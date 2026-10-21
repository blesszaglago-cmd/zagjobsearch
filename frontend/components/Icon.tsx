import type { SVGProps } from "react";

const paths = {
  "arrow-up-right": "M6 18 18 6M6 6h12v12",
  "arrow-right": "M4 12h16m-7-7 7 7-7 7",
  "arrow-left": "M20 12H4m7-7-7 7 7 7",
  "chevron-left": "m15 5-7 7 7 7",
  "chevron-right": "m9 5 7 7-7 7",
  "external-link": "M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5",
  search: "m21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  check: "m5 12 4 4L19 6",
};

type IconProps = SVGProps<SVGSVGElement> & { name: keyof typeof paths };

export default function Icon({ name, className = "", ...props }: IconProps) {
  return (
    <svg
      {...props}
      className={`ui-icon ${className}`.trim()}
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={paths[name]} />
    </svg>
  );
}
