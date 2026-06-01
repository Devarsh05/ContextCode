"use client";

import { ThemeProvider } from "next-themes";

/**
 * App-wide client providers. Theme lives here now; the React Query provider
 * will be added alongside it in the next step (data layer).
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      {/* TODO(next step): wrap children in QueryClientProvider here. */}
      {children}
    </ThemeProvider>
  );
}
