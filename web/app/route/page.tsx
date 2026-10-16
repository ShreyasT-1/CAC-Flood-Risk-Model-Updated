import type { Metadata } from "next";
import { Suspense } from "react";
import { Masthead } from "@/components/layout/masthead";
import { RouteApp } from "@/components/route/route-app";

export const metadata: Metadata = {
  title: "Route analysis · FloodLens Lifelines",
  description: "Routes from a Cape Fear address to emergency hospitals and fire stations, checked against the Florence 2018 replay. Sample data.",
};

export default function RoutePage() {
  return (
    <div className="flex min-h-[100dvh] flex-col lg:h-[100dvh]">
      <Masthead />
      <Suspense>
        <RouteApp />
      </Suspense>
    </div>
  );
}
