type FavoriteButtonProps = {
  name: string;
  favorite: boolean;
  disabled?: boolean;
  onToggle: () => void;
};

export function FavoriteButton({
  name,
  favorite,
  disabled,
  onToggle,
}: FavoriteButtonProps) {
  return (
    <button
      type="button"
      className={`layout-favorite${favorite ? " is-favorite" : ""}`}
      aria-label={`${favorite ? "Unfavorite" : "Favorite"} ${name}`}
      aria-pressed={favorite}
      title={favorite ? "Remove favorite" : "Show first in session layouts"}
      disabled={disabled}
      onClick={onToggle}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="m12 3 2.8 5.7 6.3.9-4.5 4.4 1.1 6.2-5.7-3-5.7 3 1.1-6.2L3.2 9.6l6.1-.9Z"
          fill={favorite ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="1.7"
        />
      </svg>
    </button>
  );
}
