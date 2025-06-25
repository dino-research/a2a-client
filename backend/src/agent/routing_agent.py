# ruff: noqa: E501, G201, G202
# pylint: disable=logging-fstring-interpolation
import asyncio
import json
import os
import uuid

from typing import Any, AsyncIterator

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
)
from remote_agent_connection import (
    RemoteAgentConnections,
    TaskUpdateCallback,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext


load_dotenv()


def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }

    if task_id:
        payload['message']['taskId'] = task_id

    if context_id:
        payload['message']['contextId'] = context_id
    return payload


class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote seller agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

    async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronous part of initialization."""
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    print(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'RoutingAgent':
        """Create and asynchronously initialize an instance of the RoutingAgent."""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Create an instance of the RoutingAgent."""
        model_id = 'gemini-2.5-flash-preview-04-17'
        print(f'Using hardcoded model: {model_id}')
        return Agent(
            model=model_id,
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This Routing agent orchestrates the decomposition of the user asking for weather forecast or airbnb accommodation'
            ),
            tools=[
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Generate the root instruction for the RoutingAgent."""
        current_agent = self.check_active_agent(context)
        return f"""
        **Role:** You are an expert AI Assistant and Routing Delegator. Your primary function is to help users with their inquiries by either answering directly or delegating to specialized remote agents when available.

        **Core Directives:**

        * **Direct Response Capability:** If no remote agents are available or if the query can be answered directly with your knowledge, provide a comprehensive and helpful response yourself.
        * **Task Delegation:** When appropriate remote agents are available, utilize the `send_message` function to assign actionable tasks to them.
        * **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation, assume it lacks access to the full conversation history. In such cases, enrich the task description with all necessary contextual information relevant to that specific agent.
        * **Autonomous Decision Making:** Make intelligent decisions about whether to answer directly or delegate based on the query type and available agents.
        * **Transparent Communication:** Always present complete and detailed responses to the user, whether from remote agents or your own knowledge.
        * **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, relay this confirmation request to the user.
        * **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details.
        * **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions.
        * **Comprehensive Assistance:** Answer any questions users have, using your knowledge when appropriate and delegating when specialized agents can provide better assistance.
        * **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests.
        * **Active Agent Prioritization:** If an active agent is already engaged, route subsequent related requests to that agent using the appropriate task update tool.

        **Agent Roster:**

        * Available Agents: `{self.agents}`
        * Currently Active Seller Agent: `{current_agent['active_agent']}`
                """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f'Found agent card: {card.model_dump(exclude_none=True)}')
            print('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to remote seller agent.

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry and purchase request.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        try:
            if agent_name not in self.remote_agent_connections:
                return f'Xin lỗi, agent {agent_name} không khả dụng hiện tại. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức có sẵn.'
            
            state = tool_context.state
            state['active_agent'] = agent_name
            client = self.remote_agent_connections[agent_name]

            if not client:
                return f'Xin lỗi, không thể kết nối đến agent {agent_name}. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức có sẵn.'
            
            task_id = state['task_id'] if 'task_id' in state else str(uuid.uuid4())

            if 'context_id' in state:
                context_id = state['context_id']
            else:
                context_id = str(uuid.uuid4())

            message_id = ''
            metadata = {}
            if 'input_message_metadata' in state:
                metadata.update(**state['input_message_metadata'])
                if 'message_id' in state['input_message_metadata']:
                    message_id = state['input_message_metadata']['message_id']
            if not message_id:
                message_id = str(uuid.uuid4())

            payload = {
                'message': {
                    'role': 'user',
                    'parts': [
                        {'type': 'text', 'text': task}
                    ],  # Use the 'task' argument here
                    'messageId': message_id,
                },
            }

            if task_id:
                payload['message']['taskId'] = task_id

            if context_id:
                payload['message']['contextId'] = context_id

            message_request = SendMessageRequest(
                id=message_id, params=MessageSendParams.model_validate(payload)
            )
            send_response: SendMessageResponse = await client.send_message(
                message_request=message_request
            )
            print('send_response', send_response.model_dump_json(exclude_none=True, indent=2))

            if not isinstance(send_response.root, SendMessageSuccessResponse):
                print('received non-success response. Aborting get task ')
                return f'Xin lỗi, agent {agent_name} không thể xử lý yêu cầu. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức có sẵn.'

            if not isinstance(send_response.root.result, Task):
                print('received non-task response. Aborting get task ')
                return f'Xin lỗi, agent {agent_name} trả về phản hồi không hợp lệ. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức có sẵn.'

            return send_response.root.result
            
        except Exception as e:
            print(f'Error sending message to {agent_name}: {e}')
            return f'Xin lỗi, đã xảy ra lỗi khi kết nối đến agent {agent_name}: {str(e)}. Tôi sẽ cố gắng trả lời câu hỏi của bạn dựa trên kiến thức có sẵn.'


def _get_initialized_routing_agent_sync() -> Agent:
    """Synchronously creates and initializes the RoutingAgent."""

    async def _async_main() -> Agent:
        routing_agent_instance = await RoutingAgent.create(
            remote_agent_addresses=[
                # os.getenv('AIR_AGENT_URL', 'http://localhost:10002'),
                os.getenv('SERENA_AGENT_URL', 'http://localhost:10101'),
            ]
        )
        return routing_agent_instance.create_agent()

    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're already in an event loop, create a task
        task = loop.create_task(_async_main())
        # Since we can't await in a sync function, we'll use a different approach
        # We'll store the future and resolve it later
        import threading
        import concurrent.futures
        
        # Use a thread to run the async function
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _async_main())
            return future.result()
            
    except RuntimeError as e:
        if 'no running event loop' in str(e).lower():
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(_async_main())
        elif 'asyncio.run() cannot be called from a running event loop' in str(e):
            print(
                f'Warning: Could not initialize RoutingAgent with asyncio.run(): {e}. '
                'This can happen if an event loop is already running (e.g., in Jupyter). '
                'Using lazy initialization instead.'
            )
            # Return None and handle lazy initialization later
            return None
        raise


# Use lazy initialization pattern
_root_agent = None

async def get_root_agent() -> Agent:
    """Get the root agent with lazy initialization."""
    global _root_agent
    if _root_agent is None:
        routing_agent_instance = await RoutingAgent.create(
            remote_agent_addresses=[
                # os.getenv('AIR_AGENT_URL', 'http://localhost:10002'),
                os.getenv('WEA_AGENT_URL', 'http://localhost:10001'),
            ]
        )
        _root_agent = routing_agent_instance.create_agent()
    return _root_agent

# Try to initialize synchronously, but don't fail if it can't
try:
    root_agent = _get_initialized_routing_agent_sync()
except Exception as e:
    print(f"Could not initialize root_agent synchronously: {e}")
    print("Will use lazy initialization instead.")
    root_agent = None
