import { createBrowserRouter } from "react-router-dom";
import { App } from "./App";
import { CommandCenter } from "./pages/CommandCenter";
import { YourIdentity } from "./pages/YourIdentity";
import { PublicVoice } from "./pages/PublicVoice";
import { Trends } from "./pages/Trends";
import { CrisisDMs } from "./pages/CrisisDMs";
import { AIBrief } from "./pages/AIBrief";
import { ConnectInstagram } from "./pages/ConnectInstagram";
import { GroundInput } from "./pages/GroundInput";

// 6 stubbed module routes under the app shell (architecture: all read-only views).
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <CommandCenter /> },
      { path: "identity", element: <YourIdentity /> },
      { path: "public-voice", element: <PublicVoice /> },
      { path: "trends", element: <Trends /> },
      { path: "crisis", element: <CrisisDMs /> },
      { path: "ai-brief", element: <AIBrief /> },
      { path: "ground", element: <GroundInput /> },
      { path: "connect", element: <ConnectInstagram /> },
    ],
  },
]);
