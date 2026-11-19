import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import {
  driverBadgeColors,
  driverOptionText,
  type DriverSelectOption,
} from "./driver-select-options";

type Props = {
  "aria-label": string;
  options: DriverSelectOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
};

export function DriverSelect({
  options,
  value,
  onChange,
  disabled,
  className,
  "aria-label": label,
}: Props) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const search = useRef({ text: "", time: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<CSSProperties>({});
  const selected = options.findIndex((option) => option.value === value);
  const unavailable = disabled || options.length === 0;
  const expanded = open && !unavailable;
  const close = useCallback(() => {
    search.current = { text: "", time: 0 };
    setOpen(false);
  }, []);

  function placeList() {
    const box = trigger.current?.getBoundingClientRect();
    if (!box) return;
    const width = Math.min(Math.max(box.width, 300), window.innerWidth - 16);
    const below = window.innerHeight - box.bottom - 12;
    const above = box.top - 12;
    const upwards = below < 200 && above > below;
    setPosition({
      left: Math.max(8, Math.min(box.left, window.innerWidth - width - 8)),
      width,
      maxHeight: Math.min(344, Math.max(48, upwards ? above : below)),
      ...(upwards
        ? { bottom: window.innerHeight - box.top + 6 }
        : { top: box.bottom + 6 }),
    });
  }

  function show(index = selected >= 0 ? selected : 0) {
    if (unavailable) return;
    placeList();
    setActive(index);
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    close();
    trigger.current?.focus();
  }

  useEffect(() => {
    if (!expanded) return;
    function outside(event: PointerEvent) {
      const target = event.target as Node;
      if (!trigger.current?.contains(target) && !list.current?.contains(target))
        close();
    }
    function reposition(event: Event) {
      if (!list.current?.contains(event.target as Node)) placeList();
    }
    document.addEventListener("pointerdown", outside);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      document.removeEventListener("pointerdown", outside);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [expanded, close]);

  useEffect(() => {
    if (expanded)
      list.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [active, expanded]);

  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Tab") {
      close();
      return;
    }
    if (event.key === "Escape") {
      if (expanded) {
        event.preventDefault();
        event.stopPropagation();
        close();
      }
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const index =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? options.length - 1
            : Math.max(
                0,
                Math.min(
                  options.length - 1,
                  (expanded ? active : selected) +
                    (event.key === "ArrowDown" ? 1 : -1),
                ),
              );
      if (expanded) setActive(index);
      else show(index);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (expanded) choose(active);
      else show();
      return;
    }
    if (
      event.key.length === 1 &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    ) {
      event.preventDefault();
      const now = Date.now();
      const previous =
        now - search.current.time < 700 ? search.current.text : "";
      const text =
        previous === event.key.toLowerCase()
          ? previous
          : previous + event.key.toLowerCase();
      search.current = { text, time: now };
      const start = expanded ? active : selected;
      const index = options.findIndex((_, offset) => {
        const option = options[(start + 1 + offset) % options.length];
        return driverOptionText(option)
          .toLowerCase()
          .split(/[\s#]+/)
          .some((word) => word.startsWith(text));
      });
      if (index >= 0) {
        const next = (start + 1 + index) % options.length;
        if (expanded) setActive(next);
        else show(next);
      }
    }
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        role="combobox"
        data-value={value}
        aria-label={label}
        title={selected >= 0 ? driverOptionText(options[selected]) : undefined}
        aria-haspopup="listbox"
        aria-expanded={expanded}
        aria-controls={expanded ? id : undefined}
        aria-activedescendant={
          expanded && options[active] ? `${id}-${active}` : undefined
        }
        className={`driver-select ${className ?? ""}`}
        disabled={unavailable}
        onClick={() => (expanded ? close() : show())}
        onKeyDown={keyDown}
        onBlur={close}
      >
        {selected >= 0 ? (
          <OptionContent option={options[selected]} compact />
        ) : (
          <span>Choose a driver</span>
        )}
        <span className="driver-select__chevron" aria-hidden="true">
          ⌄
        </span>
      </button>
      {expanded &&
        createPortal(
          <div
            ref={list}
            id={id}
            role="listbox"
            aria-label={label}
            className="driver-select__list"
            style={position}
          >
            {options.map((option, index) => (
              <div
                key={option.value}
                id={`${id}-${index}`}
                role="option"
                data-value={option.value}
                aria-label={driverOptionText(option)}
                aria-selected={index === selected}
                className="driver-select__option"
                data-active={index === active}
                onPointerDown={(event) => event.preventDefault()}
                onPointerMove={() => setActive(index)}
                onClick={() => choose(index)}
              >
                <OptionContent option={option} />
                <span className="driver-select__check" aria-hidden="true">
                  {index === selected ? "✓" : ""}
                </span>
              </div>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}

function OptionContent({
  option,
  compact,
}: {
  option: DriverSelectOption;
  compact?: boolean;
}) {
  const entry = option.driver;
  return (
    <span className="driver-select__content">
      {entry ? (
        <>
          <span className="driver-select__number">#{entry.car_number}</span>
          <span
            className="driver-select__badge"
            style={driverBadgeColors(entry.team_color)}
          >
            {entry.driver_abbreviation ||
              entry.driver_name?.slice(0, 3).toUpperCase() ||
              "—"}
          </span>
        </>
      ) : null}
      {!compact || !entry || option.detail ? (
        <span className="driver-select__name">
          {compact && entry ? option.detail : option.label}
        </span>
      ) : null}
    </span>
  );
}
