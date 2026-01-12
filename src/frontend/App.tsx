/**
 * App.tsx - Main Router
 * 
 * Routes:
 * / → Generator (Page 1)
 * /daw → DAW Studio (Page 2)
 */

import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, useLocation } from "react-router-dom";
import Generator from "./pages/Generator";
import DAW from "./pages/DAW";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Generator />} />
        <Route path="/daw" element={<DAW />} />
      </Routes>
    </Router>
  );
}

export default App;
