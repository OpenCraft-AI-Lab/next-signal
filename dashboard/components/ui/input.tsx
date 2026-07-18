"use client";

import { Search } from "lucide-react";
import {
  forwardRef,
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
  type HTMLAttributes,
} from "react";

import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Use `.input.mono` (Geist Mono) styling. */
  mono?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, mono, type = "text", ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn("input", mono && "mono", className)}
      {...props}
    />
  ),
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, mono, rows = 3, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn("input", mono && "mono", className)}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

interface SearchWrapProps extends HTMLAttributes<HTMLDivElement> {
  iconSize?: number;
}

/** Wraps an `<Input />` with a left-aligned search icon (design's `.search-wrap`). */
export function SearchWrap({
  className,
  iconSize = 15,
  children,
  ...props
}: SearchWrapProps) {
  return (
    <div className={cn("search-wrap", className)} {...props}>
      <Search size={iconSize} />
      {children}
    </div>
  );
}
