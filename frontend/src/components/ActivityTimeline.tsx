import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2,
  Activity,
  Info,
  Search,
  TextSearch,
  Brain,
  Pen,
  ChevronDown,
  ChevronUp,
  BarChart3,
  RefreshCw,
  CheckCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

export interface ProcessedEvent {
  title: string;
  data: any;
}

interface ActivityTimelineProps {
  processedEvents: ProcessedEvent[];
  isLoading: boolean;
}

export function ActivityTimeline({
  processedEvents,
  isLoading,
}: ActivityTimelineProps) {
  const [isTimelineCollapsed, setIsTimelineCollapsed] =
    useState<boolean>(false);
    
  /**
   * Maps event titles to appropriate icons based on the agent functions:
   * 
   * Agent Functions & Their Timeline Events:
   * 1. generate_initial_queries - Creates search queries from user input
   * 2. web_research - Performs web search using Tavily API
   * 3. analyze_research_quality - Analyzes research completeness & quality
   * 4. iterative_refinement - Generates follow-up queries if needed
   * 5. finalize_answer - Synthesizes final answer with sources
   */
  const getEventIcon = (title: string, index: number) => {
    if (index === 0 && isLoading && processedEvents.length === 0) {
      return <Loader2 className="h-4 w-4 text-neutral-400 animate-spin" />;
    }
    
    // Map to specific agent functions with colored icons
    if (title.toLowerCase().includes("generating search queries") || 
        title.toLowerCase().includes("generate_query")) {
      return <TextSearch className="h-4 w-4 text-blue-400" />;
    } else if (title.toLowerCase().includes("web research") || 
               title.toLowerCase().includes("web_research")) {
      return <Search className="h-4 w-4 text-green-400" />;
    } else if (title.toLowerCase().includes("reflection") || 
               title.toLowerCase().includes("analyze_research_quality")) {
      return <BarChart3 className="h-4 w-4 text-yellow-400" />;
    } else if (title.toLowerCase().includes("iterative_refinement") || 
               title.toLowerCase().includes("refining") ||
               title.toLowerCase().includes("follow-up")) {
      return <RefreshCw className="h-4 w-4 text-purple-400" />;
    } else if (title.toLowerCase().includes("finalizing") || 
               title.toLowerCase().includes("finalize_answer")) {
      return <CheckCircle className="h-4 w-4 text-emerald-400" />;
    } else if (title.toLowerCase().includes("thinking") || 
               title.toLowerCase().includes("processing")) {
      return <Loader2 className="h-4 w-4 text-neutral-400 animate-spin" />;
    }
    
    return <Activity className="h-4 w-4 text-neutral-400" />;
  };

  useEffect(() => {
    // Keep timeline expanded during loading or when there are events to show
    if (isLoading || processedEvents.length > 0) {
      setIsTimelineCollapsed(false);
    }
  }, [isLoading, processedEvents]);

  return (
    <Card className="border-none rounded-lg bg-neutral-700 max-h-96">
      <CardHeader>
        <CardDescription className="flex items-center justify-between">
          <div
            className="flex items-center justify-start text-sm w-full cursor-pointer gap-2 text-neutral-100"
            onClick={() => setIsTimelineCollapsed(!isTimelineCollapsed)}
          >
            Research
            {isTimelineCollapsed ? (
              <ChevronDown className="h-4 w-4 mr-2" />
            ) : (
              <ChevronUp className="h-4 w-4 mr-2" />
            )}
          </div>
        </CardDescription>
      </CardHeader>
      {!isTimelineCollapsed && (
        <ScrollArea className="max-h-96 overflow-y-auto">
          <CardContent>
            {isLoading && processedEvents.length === 0 && (
              <div className="relative pl-8 pb-4">
                <div className="absolute left-3 top-3.5 h-full w-0.5 bg-neutral-800" />
                <div className="absolute left-0.5 top-2 h-5 w-5 rounded-full bg-neutral-800 flex items-center justify-center ring-4 ring-neutral-900">
                  <Loader2 className="h-3 w-3 text-neutral-400 animate-spin" />
                </div>
                <div>
                  <p className="text-sm text-neutral-300 font-medium">
                    Initializing research agent...
                  </p>
                </div>
              </div>
            )}
            {processedEvents.length > 0 ? (
              <div className="space-y-0">
                {processedEvents.map((eventItem, index) => (
                  <div key={index} className="relative pl-8 pb-4">
                    {index < processedEvents.length - 1 ||
                    (isLoading && index === processedEvents.length - 1) ? (
                      <div className="absolute left-3 top-3.5 h-full w-0.5 bg-neutral-600" />
                    ) : null}
                    <div className="absolute left-0.5 top-2 h-6 w-6 rounded-full bg-neutral-600 flex items-center justify-center ring-4 ring-neutral-700">
                      {getEventIcon(eventItem.title, index)}
                    </div>
                    <div>
                      <p className="text-sm text-neutral-200 font-medium mb-0.5">
                        {eventItem.title}
                      </p>
                      <p className="text-xs text-neutral-300 leading-relaxed">
                        {typeof eventItem.data === "string"
                          ? eventItem.data
                          : Array.isArray(eventItem.data)
                          ? (eventItem.data as string[]).join(", ")
                          : JSON.stringify(eventItem.data)}
                      </p>
                    </div>
                  </div>
                ))}
                {isLoading && processedEvents.length > 0 && (
                  <div className="relative pl-8 pb-4">
                    <div className="absolute left-0.5 top-2 h-5 w-5 rounded-full bg-neutral-600 flex items-center justify-center ring-4 ring-neutral-700">
                      <Loader2 className="h-3 w-3 text-neutral-400 animate-spin" />
                    </div>
                    <div>
                      <p className="text-sm text-neutral-300 font-medium">
                        Processing...
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : !isLoading ? (
              <div className="flex flex-col items-center justify-center h-full text-neutral-500 pt-10">
                <Info className="h-6 w-6 mb-3" />
                <p className="text-sm">No activity to display.</p>
                <p className="text-xs text-neutral-600 mt-1">
                  Timeline will update during agent processing.
                </p>
              </div>
            ) : null}
          </CardContent>
        </ScrollArea>
      )}
    </Card>
  );
}
