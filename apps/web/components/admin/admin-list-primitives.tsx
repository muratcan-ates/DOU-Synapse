"use client";

import { useState } from "react";
import { ErrorNote } from "@/components/page-state";
import { Button, Input, Select } from "@/components/ui";
import { type Resource } from "@/lib/use-resource";

export const PAGE_SIZE = 25;
export function AdminListFrame<T>({
  resource,
  children,
}: {
  resource: Resource<T>;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      {resource.refreshError && (
        <ErrorNote
          message={resource.refreshError}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
          onRetry={resource.reload}
        />
      )}
      {children}
    </div>
  );
}

export function AdminFilter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="block max-w-xs text-xs font-medium text-fg-muted">
      {label}
      <Select
        wrapperClassName="mt-2"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    </label>
  );
}

export function AdminTextFilter({
  label,
  placeholder,
  appliedValue,
  onApply,
}: {
  label: string;
  placeholder: string;
  appliedValue: string;
  onApply: (value: string) => void;
}) {
  const [draft, setDraft] = useState(appliedValue);

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-surface px-5 py-5"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft.trim());
      }}
    >
      <label className="min-w-0 flex-1 text-sm font-medium text-fg-muted">
        {label}
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={placeholder}
          className="mt-2"
        />
      </label>
      <Button type="submit" variant="secondary">
        Uygula
      </Button>
      {appliedValue && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setDraft("");
            onApply("");
          }}
        >
          Temizle
        </Button>
      )}
    </form>
  );
}
