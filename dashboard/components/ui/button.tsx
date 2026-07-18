"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Variants composed of the design's `.btn` class plus modifier suffixes
// (`.btn.primary`, `.btn.ghost`, etc). The design CSS lives in globals.css;
// we just toggle the class names here.
const buttonVariants = cva("btn", {
  variants: {
    variant: {
      default: "",
      primary: "primary",
      solid: "solid",
      ghost: "ghost",
      danger: "danger",
      icon: "icon",
    },
    size: {
      default: "",
      sm: "sm",
      lg: "",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
