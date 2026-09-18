import { useState, type FormEvent } from "react";

interface ChatInputProps {
  onSubmit: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setText("");
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder='Try "undo my last commit" or "open an issue saying login is broken"'
        disabled={disabled}
        autoFocus
      />
      <button type="submit" disabled={disabled || !text.trim()}>
        Ask
      </button>
    </form>
  );
}
