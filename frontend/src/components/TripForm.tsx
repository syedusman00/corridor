import { MapPinned, Scale, Clock3, Route, CalendarDays } from "lucide-react";
import type { AnalyzeRequest } from "../types";

interface Props {
  value: AnalyzeRequest;
  loading: boolean;
  onChange: (next: AnalyzeRequest) => void;
  onSubmit: () => void;
}

const INTERVALS: Array<10 | 25 | 50> = [10, 25, 50];

function splitDeparture(value: string): { date: string; time: string } {
  const [date = "", timePart = ""] = (value || "").split("T");
  const time = (timePart || "00:00").slice(0, 5);
  return { date, time };
}

export function TripForm({ value, loading, onChange, onSubmit }: Props) {
  const { date, time } = splitDeparture(value.departure);

  function setDate(nextDate: string) {
    onChange({ ...value, departure: `${nextDate}T${time || "00:00"}` });
  }

  function setTime(nextTime: string) {
    onChange({
      ...value,
      departure: `${date || new Date().toISOString().slice(0, 10)}T${nextTime}`,
    });
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <Field
        label="Origin"
        icon={<MapPinned size={16} />}
        value={value.origin}
        placeholder="Chicago, IL"
        onChange={(origin) => onChange({ ...value, origin })}
      />
      <Field
        label="Destination"
        icon={<Route size={16} />}
        value={value.destination}
        placeholder="Denver, CO"
        onChange={(destination) => onChange({ ...value, destination })}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            <CalendarDays size={14} /> Departure date
          </span>
          <input
            type="date"
            required
            className="rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            <Clock3 size={14} /> Departure time
          </span>
          <input
            type="time"
            required
            step={60}
            className="rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
          <Scale size={14} /> Load weight (lbs)
        </span>
        <input
          type="number"
          min={0}
          step={100}
          required
          className="rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
          value={value.load_lbs}
          onChange={(e) =>
            onChange({ ...value, load_lbs: Number(e.target.value) })
          }
        />
      </label>

      <fieldset>
        <legend className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
          Weather checkpoint interval
        </legend>
        <div className="grid grid-cols-3 gap-2">
          {INTERVALS.map((n) => {
            const active = value.interval_miles === n;
            return (
              <button
                key={n}
                type="button"
                onClick={() => onChange({ ...value, interval_miles: n })}
                className={
                  active
                    ? "rounded-xl bg-[var(--color-accent)] px-3 py-2 text-sm font-semibold text-white shadow-sm"
                    : "rounded-xl border border-[var(--color-line)] bg-white px-3 py-2 text-sm font-medium text-[var(--color-ink)] hover:border-[var(--color-accent)]"
                }
              >
                {n} mi
              </button>
            );
          })}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={loading || !value.origin || !value.destination}
        className="mt-1 inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--color-ink)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--color-accent-deep)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Analyzing routes…
          </>
        ) : (
          "Find safest truck routes"
        )}
      </button>
    </form>
  );
}

function Field({
  label,
  icon,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  icon: React.ReactNode;
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
        {icon} {label}
      </span>
      <input
        type="text"
        required
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none transition focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
      />
    </label>
  );
}
