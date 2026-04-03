"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownMessage({ content, className }: { content: string; className?: string }) {
  return (
    <div className={className}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        h1: ({ children }) => <h1 className="mb-2 mt-3 text-base font-bold">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-2 mt-3 text-sm font-bold">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-1 mt-2 text-sm font-semibold">{children}</h3>,
        ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="text-sm">{children}</li>,
        code: ({ className: cls, children, ...props }) => {
          const isBlock = cls?.startsWith("language-");
          if (isBlock) {
            return (
              <pre className="my-2 overflow-x-auto rounded-lg border border-af-border/40 bg-black/30 p-3">
                <code className="font-mono text-xs text-af-primary">{children}</code>
              </pre>
            );
          }
          return (
            <code
              {...props}
              className="rounded bg-black/20 px-1 py-0.5 font-mono text-xs text-af-primary"
            >
              {children}
            </code>
          );
        },
        pre: ({ children }) => <>{children}</>,
        blockquote: ({ children }) => (
          <blockquote className="my-2 border-l-2 border-af-primary/40 pl-3 italic text-af-muted">
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-af-primary underline underline-offset-2 hover:opacity-80"
          >
            {children}
          </a>
        ),
        strong: ({ children }) => <strong className="font-bold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        hr: () => <hr className="my-3 border-af-border/30" />,
      }}
    >
      {content}
    </ReactMarkdown>
    </div>
  );
}
