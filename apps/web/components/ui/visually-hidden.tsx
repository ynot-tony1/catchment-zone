import * as React from "react";

/** Renders content for assistive technology only. Used for chart data-table
 * summaries and other content that has a visual equivalent (a chart) but
 * needs a text alternative for screen reader users. */
function VisuallyHidden(props: Omit<React.ComponentProps<"span">, "className">) {
  return (
    <span
      style={{
        position: "absolute",
        width: 1,
        height: 1,
        padding: 0,
        margin: -1,
        overflow: "hidden",
        clip: "rect(0, 0, 0, 0)",
        whiteSpace: "nowrap",
        borderWidth: 0,
      }}
      {...props}
    />
  );
}

export { VisuallyHidden };
