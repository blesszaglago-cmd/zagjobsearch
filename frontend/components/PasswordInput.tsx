"use client";

import { useState, type InputHTMLAttributes } from "react";
import Icon from "@/components/Icon";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "id"> & {
  id: string;
  visibilityLabel?: string;
};

export default function PasswordInput({
  id,
  visibilityLabel = "password",
  ...props
}: Props) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="password-field">
      <input {...props} id={id} type={visible ? "text" : "password"} />
      <button
        className="password-toggle"
        type="button"
        aria-label={`${visible ? "Hide" : "Show"} ${visibilityLabel}`}
        aria-controls={id}
        aria-pressed={visible}
        onClick={() => setVisible((value) => !value)}
      >
        <Icon name={visible ? "eye-off" : "eye"} />
      </button>
    </span>
  );
}
