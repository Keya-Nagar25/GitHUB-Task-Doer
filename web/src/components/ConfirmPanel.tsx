import { useState } from "react";
import { GITHUB_API_ACTIONS, type ResolvedAction } from "../types";
import { commandPreview } from "../commandPreview";

interface ConfirmPanelProps {
  resolvedAction: ResolvedAction;
  executing: boolean;
  executed: boolean;
  onConfirm: () => void;
}

export function ConfirmPanel({ resolvedAction, executing, executed, onConfirm }: ConfirmPanelProps) {
  const [doubleConfirmChecked, setDoubleConfirmChecked] = useState(false);
  const [copied, setCopied] = useState(false);

  const canExecuteDirectly = GITHUB_API_ACTIONS.has(resolvedAction.action);
  const command = commandPreview(resolvedAction);
  const confirmDisabled =
    executing || executed || (resolvedAction.requires_double_confirmation && !doubleConfirmChecked);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can fail (permissions, insecure context) -- the
      // command is still visible and selectable, so this is a soft failure.
    }
  };

  return (
    <section className={`confirm-panel${resolvedAction.destructive ? " confirm-panel--destructive" : ""}`}>
      <div className="confirm-panel__command">
        <code>{command}</code>
      </div>

      <p className="confirm-panel__explanation">{resolvedAction.explanation}</p>

      {resolvedAction.clarifying_question && (
        <p className="confirm-panel__note">{resolvedAction.clarifying_question}</p>
      )}

      {resolvedAction.destructive && (
        <p className="confirm-panel__warning">
          This action is destructive -- it can discard work. Double-check before running it.
        </p>
      )}

      {resolvedAction.requires_double_confirmation && (
        <label className="confirm-panel__double-confirm">
          <input
            type="checkbox"
            checked={doubleConfirmChecked}
            onChange={(e) => setDoubleConfirmChecked(e.target.checked)}
          />
          I understand this may permanently discard work
        </label>
      )}

      {canExecuteDirectly ? (
        <button className="confirm-panel__button" disabled={confirmDisabled} onClick={onConfirm}>
          {executed ? "Done" : executing ? "Running..." : "Confirm & Run"}
        </button>
      ) : (
        <div className="confirm-panel__local-only">
          <p>
            This needs a local working copy -- run it yourself, or use the GitHub Task Doer VS Code
            extension to execute it directly.
          </p>
          <button className="confirm-panel__button confirm-panel__button--secondary" onClick={handleCopy}>
            {copied ? "Copied" : "Copy command"}
          </button>
        </div>
      )}
    </section>
  );
}
