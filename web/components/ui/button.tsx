import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex min-h-11 w-full items-center justify-center rounded-xl font-ui text-sm font-semibold transition duration-200 ease-out focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue/25 active:scale-[0.98] md:w-auto",
  {
    variants: {
      variant: {
        primary: "bg-blue px-6 text-white hover:-translate-y-0.5 hover:bg-[#244d86] hover:shadow-lift",
        secondary: "border border-ink/15 bg-white px-6 text-ink hover:bg-soft-blue",
        ghost: "px-4 text-ink/75 hover:bg-soft-blue hover:text-blue",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

type Props = React.ComponentProps<"button"> & VariantProps<typeof button>;

export const Button = ({ variant, className, ...props }: Props) => (
  <button className={cn(button({ variant }), className)} {...props} />
);
