export default function PageTransition({ children }: { children: React.ReactNode }) {
  return <div className="animate-fadeIn">{children}</div>;
}
