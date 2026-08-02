import { Suspense, lazy, type ComponentType } from "react";
import { createBrowserRouter } from "react-router";
import { Layout } from "@/components/layout/Layout";

const Home = lazy(() => import("@/pages/Home").then((m) => ({ default: m.Home })));
const Agent = lazy(() => import("@/pages/Agent").then((m) => ({ default: m.Agent })));
const RunDetail = lazy(() =>
  import("@/pages/RunDetail").then((m) => ({ default: m.RunDetail })),
);
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
const Runtime = lazy(() =>
  import("@/pages/Runtime").then((m) => ({ default: m.Runtime })),
);
const Reports = lazy(() =>
  import("@/pages/Reports").then((m) => ({ default: m.Reports })),
);
const CryptoMarket = lazy(() =>
  import("@/pages/CryptoMarket").then((m) => ({ default: m.CryptoMarket })),
);
const Portfolio = lazy(() =>
  import("@/pages/Portfolio").then((m) => ({ default: m.Portfolio })),
);
const AIScalpTrader = lazy(() =>
  import("@/pages/AIScalpTrader").then((m) => ({ default: m.AIScalpTrader })),
);

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
      Loading…
    </div>
  );
}

function wrap(Component: ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: wrap(Agent) },
      { path: "/about", element: wrap(Home) },
      { path: "/agent", element: wrap(Agent) },
      { path: "/ai-scalp-trader", element: wrap(AIScalpTrader) },
      { path: "/runtime", element: wrap(Runtime) },
      { path: "/markets", element: wrap(CryptoMarket) },
      { path: "/portfolio", element: wrap(Portfolio) },
      { path: "/reports", element: wrap(Reports) },
      { path: "/settings", element: wrap(Settings) },
      { path: "/runs/:runId", element: wrap(RunDetail) },
    ],
  },
]);
