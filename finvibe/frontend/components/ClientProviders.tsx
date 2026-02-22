"use client";

import { AuthProvider } from "@/lib/auth";
import Navbar from "@/components/Navbar";

export default function ClientProviders({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <Navbar />
      {children}
    </AuthProvider>
  );
}
