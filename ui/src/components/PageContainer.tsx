import { cn } from "../lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  /** Default p-6 sm:p-10. Override if a page needs custom padding. */
  className?: string;
  /** max-w-7xl by default. Pass e.g. "max-w-4xl" for narrower pages. */
  maxWidth?: string;
}

/** Standard admin-page wrapper.
 *
 *  `min-h-full` makes the page always fill its <main> parent so the gray
 *  Shell background never bleeds through below the content; `pb-12` adds a
 *  consistent breathing-room band at the end.
 *
 *  Use on every admin page — replaces ad-hoc p-6/pb-24/max-w-* wrappers.
 */
export default function PageContainer({
  children,
  className,
  maxWidth = "max-w-7xl",
}: PageContainerProps) {
  return (
    <div
      className={cn(
        "min-h-full flex flex-col p-6 sm:p-10 pb-12 mx-auto w-full",
        maxWidth,
        className,
      )}
    >
      {children}
    </div>
  );
}
