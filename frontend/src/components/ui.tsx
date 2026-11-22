import { clsx } from "clsx";
import { CircleCheck, CircleHelp, CircleX, Clock, LoaderCircle, TriangleAlert } from "lucide-react";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import type { Status, Verdict } from "../lib/types";

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={clsx("rounded-xl border border-line bg-surface p-5 shadow-[0_1px_0_rgba(0,0,0,0.02)]", className)}
      {...rest}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="mb-4 flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-[15px] text-ink-2">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
}) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        buttonTone(variant),
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function buttonTone(variant: ButtonVariant) {
  return {
    primary: "bg-accent text-white hover:brightness-110 active:brightness-95",
    secondary: "border border-line bg-surface text-ink hover:bg-surface-2",
    ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
    danger: "border border-line bg-surface text-ink hover:wash-critical",
  }[variant];
}

type Tone = "neutral" | "accent" | "good" | "critical" | "warning";

export function Badge({
  tone = "neutral",
  icon,
  children,
  className,
  title,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={clsx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium text-ink",
        {
          neutral: "bg-surface-2 text-ink-2",
          accent: "wash-accent",
          good: "wash-good",
          critical: "wash-critical",
          warning: "wash-warning",
        }[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/** Status colors never carry meaning alone: every verdict pairs an icon with a label. */
export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  if (verdict === "held")
    return (
      <Badge tone="good" icon={<CircleCheck className="size-3.5 text-good" aria-hidden />}>
        Held
      </Badge>
    );
  if (verdict === "failed")
    return (
      <Badge tone="critical" icon={<CircleX className="size-3.5 text-critical" aria-hidden />}>
        Failed
      </Badge>
    );
  return (
    <Badge icon={<CircleHelp className="size-3.5 text-ink-3" aria-hidden />}>Unclear</Badge>
  );
}

export function StatusBadge({ status, happened }: { status: Status; happened: boolean | null }) {
  if (status === "reviewed") {
    return happened ? (
      <Badge tone="good" icon={<CircleCheck className="size-3.5 text-good" aria-hidden />}>
        Happened
      </Badge>
    ) : (
      <Badge tone="critical" icon={<CircleX className="size-3.5 text-critical" aria-hidden />}>
        Didn't happen
      </Badge>
    );
  }
  if (status === "due")
    return (
      <Badge tone="warning" icon={<TriangleAlert className="size-3.5 text-ink" aria-hidden />}>
        Review due
      </Badge>
    );
  return (
    <Badge icon={<Clock className="size-3.5 text-ink-3" aria-hidden />}>Open</Badge>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-ink-2" role="status">
      <LoaderCircle className="size-4 animate-spin" aria-hidden />
      {label}…
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      {icon && <div className="mb-1 text-ink-3">{icon}</div>}
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {body && <div className="max-w-md text-sm text-ink-2">{body}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <Card className="wash-critical">
      <div className="flex items-start gap-3">
        <TriangleAlert className="mt-0.5 size-5 shrink-0 text-critical" aria-hidden />
        <div>
          <p className="font-medium text-ink">Couldn't load this</p>
          <p className="mt-1 text-sm text-ink-2">{message}</p>
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: ReactNode; title?: string }[];
  label: string;
  size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-surface-2 p-0.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.title}
            onClick={() => onChange(option.value)}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-md font-medium transition",
              size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
              active ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: ReactNode;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-ink-3">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
