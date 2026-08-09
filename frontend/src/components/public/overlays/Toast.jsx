import { CheckIcon } from "../shell/icons.jsx";

export default function Toast({ message, onView }) {
  if (!message) return null;
  return (
    <div className="vs-toast" role="status" aria-live="polite">
      <span className="vs-toast__mark">
        <CheckIcon size={13} />
      </span>
      <span className="vs-toast__text">{message}</span>
      <button type="button" className="vs-toast__action" onClick={onView}>
        عرض العربة
      </button>
    </div>
  );
}
