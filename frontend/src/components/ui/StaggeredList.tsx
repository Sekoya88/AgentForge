// frontend/src/components/ui/StaggeredList.tsx
import React from "react";

interface StaggeredListProps {
  children: React.ReactNode[];
  baseDelay?: number; // ms per item, default 50
}

export function StaggeredList({ children, baseDelay = 50 }: StaggeredListProps) {
  return (
    <>
      {React.Children.map(children, (child, i) =>
        React.isValidElement(child)
          ? React.cloneElement(child as React.ReactElement<{ className?: string; style?: React.CSSProperties }>, {
              className: [
                (child as React.ReactElement<{ className?: string }>).props.className ?? "",
                "af-stagger-item",
              ]
                .filter(Boolean)
                .join(" "),
              style: {
                ...(child as React.ReactElement<{ style?: React.CSSProperties }>).props.style,
                animationDelay: `${i * baseDelay}ms`,
              },
            })
          : child,
      )}
    </>
  );
}
