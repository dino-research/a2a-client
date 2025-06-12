import { useState, useEffect, useRef, useCallback } from "react";
import { ProcessedEvent } from "@/components/ActivityTimeline";
import { WelcomeScreen } from "@/components/WelcomeScreen";
import { ChatMessagesView } from "@/components/ChatMessagesView";

// Define our own Message type since we're not using LangChain anymore
interface Message {
  type: "human" | "ai";
  content: string;
  id: string;
  sources?: Array<{
    title: string;
    url: string;
    snippet?: string;
    label?: string;
  }>;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [processedEventsTimeline, setProcessedEventsTimeline] = useState<
    ProcessedEvent[]
  >([]);
  const [historicalActivities, setHistoricalActivities] = useState<
    Record<string, ProcessedEvent[]>
  >({});
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const hasFinalizeEventOccurredRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollViewport = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollViewport) {
        scrollViewport.scrollTop = scrollViewport.scrollHeight;
      }
    }
  }, [messages]);

  useEffect(() => {
    if (
      hasFinalizeEventOccurredRef.current &&
      !isLoading &&
      messages.length > 0
    ) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage && lastMessage.type === "ai" && lastMessage.id) {
        setHistoricalActivities((prev) => ({
          ...prev,
          [lastMessage.id!]: [...processedEventsTimeline],
        }));
      }
      hasFinalizeEventOccurredRef.current = false;
    }
  }, [messages, isLoading, processedEventsTimeline]);

  const handleSubmit = useCallback(
    async (submittedInputValue: string, effort: string, model: string) => {
      console.log("handleSubmit called with:", { submittedInputValue, effort, model });
      
      if (!submittedInputValue.trim()) {
        console.log("Empty input, returning");
        return;
      }
      
      setIsLoading(true);
      setProcessedEventsTimeline([]);
      hasFinalizeEventOccurredRef.current = false;

      // Add user message immediately
      const userMessage: Message = {
        type: "human",
        content: submittedInputValue,
        id: Date.now().toString(),
      };

      const newMessages = [...messages, userMessage];
      setMessages(newMessages);

      // Convert effort to parameters
      let initial_search_query_count = 0;
      let max_research_loops = 0;
      switch (effort) {
        case "low":
          initial_search_query_count = 1;
          max_research_loops = 1;
          break;
        case "medium":
          initial_search_query_count = 3;
          max_research_loops = 3;
          break;
        case "high":
          initial_search_query_count = 5;
          max_research_loops = 10;
          break;
      }

      const payload = {
        messages: newMessages,
        initial_search_query_count,
        max_research_loops,
        reasoning_model: model,
      };

      console.log("Sending request to backend:", payload);

      try {
        // Create abort controller
        abortControllerRef.current = new AbortController();

        const response = await fetch("/assistants/agent/runs", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Response body is not readable");
        }

        let assistantMessage: Message | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataContent = line.slice(6);
              
              // Skip parsing [DONE] marker
              if (dataContent === '[DONE]') {
                console.log("Received [DONE] marker, stream complete");
                continue;
              }
              
              try {
                const data = JSON.parse(dataContent);
                console.log("Received event:", data);

                if (data.event_type) {
                  handleStreamEvent(data);
                }

                // Check if this is the final message
                if (data.event_type === "message" && data.data.type === "ai") {
                  assistantMessage = {
                    type: "ai",
                    content: data.data.content,
                    id: data.data.id,
                    sources: data.data.sources || [],
                  };
                }
              } catch (e) {
                console.error("Error parsing SSE data:", e, "Content:", dataContent);
              }
            }
          }
        }

        // Add assistant message if we got one
        if (assistantMessage) {
          setMessages(prev => [...prev, assistantMessage!]);
        }

      } catch (error: unknown) {
        if (error instanceof Error && error.name === 'AbortError') {
          console.log('Request was cancelled');
        } else {
          console.error("Error sending request:", error);
          // Add error message
          const errorMessage: Message = {
            type: "ai",
            content: `Xin lỗi, đã xảy ra lỗi: ${error instanceof Error ? error.message : 'Unknown error'}`,
            id: Date.now().toString(),
          };
          setMessages(prev => [...prev, errorMessage]);
        }
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [messages]
  );

  const handleStreamEvent = (data: {
    event_type?: string;
    data?: {
      query_list?: string[];
      query?: string;
      status?: string;
      sources_gathered?: Array<{ label?: string; title?: string }>;
      is_sufficient?: boolean;
      follow_up_queries?: string[];
      confidence?: number;
      answer?: string;
    };
  }) => {
    let processedEvent: ProcessedEvent | null = null;

    if (data.event_type === "generate_query" && data.data?.query_list) {
      processedEvent = {
        title: "Generating Search Queries",
        data: data.data.query_list.join(", "),
      };
    } else if (data.event_type === "generate_query" && data.data?.query) {
      processedEvent = {
        title: "Generating Search Queries",
        data: `Creating search queries for: ${data.data.query}`,
      };
    } else if (data.event_type === "web_research") {
      if (data.data?.status === "searching") {
        processedEvent = {
          title: "Web Research",
          data: `Searching for: ${data.data.query || "information"}`,
        };
      } else if (data.data?.sources_gathered) {
        const sources = data.data.sources_gathered || [];
        const numSources = sources.length;
        const uniqueLabels = [
          ...new Set(sources.map((s) => s.label || s.title).filter(Boolean)),
        ];
        const exampleLabels = uniqueLabels.slice(0, 3).join(", ");
        processedEvent = {
          title: "Web Research",
          data: `Gathered ${numSources} sources. Related to: ${
            exampleLabels || "N/A"
          }.`,
        };
      } else if (data.data?.status === "refining") {
        processedEvent = {
          title: "Web Research",
          data: "Conducting follow-up research for more details",
        };
      }
    } else if (data.event_type === "reflection") {
      if (data.data?.status === "analyzing") {
        processedEvent = {
          title: "Reflection",
          data: "Analyzing research quality and completeness",
        };
      } else {
        const confidence = data.data?.confidence ? Math.round(data.data.confidence * 100) : 0;
        processedEvent = {
          title: "Reflection",
          data: data.data?.is_sufficient
            ? `Research quality: ${confidence}% - Sufficient for final answer`
            : `Research quality: ${confidence}% - Need more information: ${(data.data?.follow_up_queries || []).join(", ")}`,
        };
      }
    } else if (data.event_type === "finalize_answer") {
      if (data.data?.status === "synthesizing") {
        processedEvent = {
          title: "Finalizing Answer",
          data: "Synthesizing research results into comprehensive answer",
        };
      } else {
        processedEvent = {
          title: "Finalizing Answer",
          data: "Presenting final answer with sources",
        };
        hasFinalizeEventOccurredRef.current = true;
      }
          }

      if (processedEvent) {
        setProcessedEventsTimeline((prevEvents) => [
          ...prevEvents,
          processedEvent!,
        ]);
      }
  };

  const handleCancel = useCallback(() => {
    console.log("Cancelling request");
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsLoading(false);
    setProcessedEventsTimeline([]);
  }, []);

  const handleNewSearch = useCallback(() => {
    if (isLoading) {
      handleCancel();
    }
    setMessages([]);
    setProcessedEventsTimeline([]);
    setHistoricalActivities({});
    hasFinalizeEventOccurredRef.current = false;
  }, [isLoading, handleCancel]);

  return (
    <div className="flex h-screen bg-neutral-800 text-neutral-100 font-sans antialiased overflow-hidden">
      <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full h-full">
        <div
          className={`flex-1 overflow-y-auto overflow-x-hidden ${
            messages.length === 0 ? "flex" : ""
          }`}
        >
          {messages.length === 0 ? (
            <WelcomeScreen
              handleSubmit={handleSubmit}
              isLoading={isLoading}
              onCancel={handleCancel}
            />
          ) : (
            <ChatMessagesView
              messages={messages}
              isLoading={isLoading}
              scrollAreaRef={scrollAreaRef}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              onNewSearch={handleNewSearch}
              liveActivityEvents={processedEventsTimeline}
              historicalActivities={historicalActivities}
            />
          )}
        </div>
      </main>
    </div>
  );
}
