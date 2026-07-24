import { Fragment, ReactNode } from "react";
import { Sparkles, Hourglass } from "lucide-react";
import { ChatMessage } from "../lib/api";

/** Minimal, safe markdown: **bold** + line breaks, rendered as React nodes (no innerHTML). */
function renderRich(text: string): ReactNode {
  return text.split("\n").map((line, lineIndex) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
    return (
      <Fragment key={lineIndex}>
        {lineIndex > 0 && <br />}
        {parts.map((part, i) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={i} className="text-steel-dark font-semibold">
              {part.slice(2, -2)}
            </strong>
          ) : (
            <Fragment key={i}>{part}</Fragment>
          ),
        )}
      </Fragment>
    );
  });
}

type ChatTimelineProps = {
  messages: ChatMessage[];
  typing: boolean;
  assistantName: string;
};

export function ChatTimeline({ messages, typing, assistantName }: ChatTimelineProps) {
  return (
    <div className="w-full lg:w-3/5 ml-0 mr-auto lg:ml-12 space-y-8 flex flex-col pb-12">
      {messages.map((message) =>
        message.role === "user" ? (
          <div
            key={message.id}
            className="flex flex-col items-end self-end max-w-[90%] space-y-1"
          >
            <div className="bg-navy-900 border border-navy-700 text-steel-dark rounded-2xl py-3 px-5 text-sm shadow-sm leading-relaxed">
              {renderRich(message.content)}
            </div>
            <span className="text-[10px] text-steel mr-1">You</span>
          </div>
        ) : (
          <div key={message.id} className="flex gap-3.5 self-start w-full items-start">
            <div className="w-6 h-6 rounded-full bg-steel-dark flex items-center justify-center text-white shrink-0 mt-1 shadow-sm">
              <Sparkles size={11} />
            </div>
            <div className="flex-1 flex flex-col space-y-2">
              <div className="text-steel-dark text-sm leading-relaxed">
                {renderRich(message.content)}
              </div>
              <span className="text-[10px] text-steel">
                {assistantName} · Assistant
              </span>
            </div>
          </div>
        ),
      )}

      {typing && (
        <div className="flex gap-3.5 self-start w-full items-start">
          <div className="w-6 h-6 rounded-full bg-steel-dark flex items-center justify-center text-white shrink-0 mt-1 shadow-sm">
            <Hourglass size={10} className="animate-spin" />
          </div>
          <div className="py-1 px-2 text-sm flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-steel-highlight animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-steel-highlight animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-steel-highlight animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      )}
    </div>
  );
}
