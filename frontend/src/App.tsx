import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Signals } from "./pages/Signals";
import { SignalDetail } from "./pages/SignalDetail";
import { Research } from "./pages/Research";
import { Journal } from "./pages/Journal";
import { Sessions } from "./pages/Sessions";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/signals/:id" element={<SignalDetail />} />
          <Route path="/research" element={<Research />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/sessions" element={<Sessions />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
