// src/pages/index.js
import { useState, useEffect, useContext } from "react";
import axios from "axios";
import AuthContext from "../context/AuthContext";
import { RiskChart } from "../components/RiskChart";
import { TimelineChart } from "../components/TimelineChart";

// --- LOGIN FORM COMPONENT ---
// This component is shown to users who are not logged in.
const LoginForm = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useContext(AuthContext);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const success = await login(email, password);
    if (!success) {
      setError("Invalid credentials. Please try again.");
    }
    setLoading(false);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-md p-8 space-y-6 bg-white rounded-lg shadow-xl">
        <h1 className="text-3xl font-bold text-center text-gray-800">
          VoIP Tracer Login
        </h1>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 mt-1 text-gray-900 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 mt-1 text-gray-900 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          {error && <p className="text-sm text-red-600 text-center">{error}</p>}
          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full px-4 py-2 font-semibold text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:bg-indigo-400"
            >
              {loading ? "Logging in..." : "Log In"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// --- MAIN DASHBOARD COMPONENT ---
// This component is shown to users who are successfully logged in.
const Dashboard = () => {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [pcapFile, setPcapFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");

  const [riskData, setRiskData] = useState(null);
  const [timelineData, setTimelineData] = useState(null);

  const { token, logout, apiClient } = useContext(AuthContext);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [callsRes, riskRes, timelineRes] = await Promise.all([
        apiClient.get("/calls?limit=100"),
        apiClient.get("/stats/risk_distribution"),
        apiClient.get("/stats/timeline"),
      ]);

      setCalls(callsRes.data.calls || []);
      setRiskData(riskRes.data);
      setTimelineData(timelineRes.data);
    } catch (err) {
      setError("Failed to fetch data. Ensure data exists in Elasticsearch.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchTerm) {
      fetchCalls();
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get(`/search?ip=${searchTerm}`);
      setCalls(response.data.results || []);
    } catch (err) {
      setError("Failed to perform search.");
    } finally {
      setLoading(false);
    }
  };

  const handlePcapUpload = async (e) => {
    e.preventDefault();
    if (!pcapFile) {
      setUploadStatus("Please select a file first.");
      return;
    }
    setUploadStatus("Uploading...");

    const formData = new FormData();
    formData.append("file", pcapFile);

    try {
      const response = await apiClient.post("/pcap/upload", formData);
      setUploadStatus(
        response.data.message + " Refreshing data in 15 seconds..."
      );
      setTimeout(() => {
        fetchData();
        setUploadStatus("");
      }, 15000);
    } catch (err) {
      setUploadStatus("Upload failed. Please try again.");
    }
  };

  useEffect(() => {
    if (token) {
      fetchData();
    }
  }, [token]);

  // Helper to render tags with different colors
  const renderTags = (tags) => {
    if (!tags) return null;
    return tags.map((tag) => {
      let color = "bg-gray-500"; // Default
      if (tag === "blacklist_match") color = "bg-red-600";
      if (tag === "high_risk_country") color = "bg-yellow-600";
      if (tag === "ml_anomaly") color = "bg-purple-600"; // Special color for ML!
      return (
        <span
          key={tag}
          className={`px-2 py-1 text-xs font-semibold text-white ${color} rounded-full mr-1`}
        >
          {tag.replace("_", " ")}
        </span>
      );
    });
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-md">
        <nav className="container mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-indigo-600">
            VoIP Tracer Dashboard
          </h1>
          <button
            onClick={logout}
            className="px-4 py-2 font-semibold text-indigo-600 bg-indigo-100 rounded-md hover:bg-indigo-200"
          >
            Log Out
          </button>
        </nav>
      </header>

      <main className="container mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-1 bg-white p-4 rounded-lg shadow-xl flex items-center justify-center">
            {riskData ? (
              <RiskChart chartData={riskData} />
            ) : (
              <p>No risk data.</p>
            )}
          </div>
          <div className="lg:col-span-2 bg-white p-4 rounded-lg shadow-xl flex items-center justify-center">
            {timelineData ? (
              <TimelineChart chartData={timelineData} />
            ) : (
              <p>No timeline data.</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-xl">
            <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-4 mb-4">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by IP address..."
                className="flex-grow px-3 py-2 text-gray-900 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              />
              <div className="flex space-x-2">
                <button
                  onClick={handleSearch}
                  className="w-full sm:w-auto px-6 py-2 font-semibold text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
                >
                  Search
                </button>
                <button
                  onClick={() => {
                    setSearchTerm("");
                    fetchData();
                  }}
                  className="w-full sm:w-auto px-4 py-2 font-semibold text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300"
                >
                  Clear
                </button>
              </div>
            </div>

            {loading && <p className="text-center p-4">Loading data...</p>}
            {error && <p className="text-center p-4 text-red-500">{error}</p>}

            {!loading && !error && (
              <div className="overflow-x-auto">
                <table className="w-full text-left table-auto">
                  <thead className="bg-gray-200 text-gray-700">
                    <tr>
                      <th className="px-4 py-2">Risk</th>
                      <th className="px-4 py-2">Source IP</th>
                      <th className="px-4 py-2">Destination IP</th>
                      <th className="px-4 py-2">Timestamp</th>
                      <th className="px-4 py-2">Source File</th>
                      <th className="px-4 py-2">Tags</th>
                    </tr>
                  </thead>
                  <tbody className="text-gray-800">
                    {calls.length > 0 ? (
                      calls.map((call, index) => (
                        <tr
                          key={call.uid || index}
                          className={`border-b ${
                            call.risk_score > 40
                              ? "bg-red-50 hover:bg-red-100"
                              : "hover:bg-gray-50"
                          }`}
                        >
                          <td
                            className={`px-4 py-2 font-bold ${
                              call.risk_score > 40
                                ? "text-red-700"
                                : "text-green-700"
                            }`}
                          >
                            {call.risk_score}
                          </td>
                          <td className="px-4 py-2">{call["id.orig_h"]}</td>
                          <td className="px-4 py-2">{call["id.resp_h"]}</td>
                          <td className="px-4 py-2 text-sm text-gray-600">
                            {new Date(call.ts * 1000).toLocaleString()}
                          </td>
                          <td className="px-4 py-2 text-xs">
                            {call["source"]}
                          </td>
                          <td className="px-4 py-2">{renderTags(call.tags)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan="5"
                          className="text-center p-4 text-gray-500"
                        >
                          No call data found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="lg:col-span-1">
            <div className="bg-white p-6 rounded-lg shadow-xl">
              <h2 className="text-xl font-bold text-gray-800 mb-4">
                Analyze PCAP File
              </h2>
              <form onSubmit={handlePcapUpload}>
                <input
                  type="file"
                  onChange={(e) => setPcapFile(e.target.files[0])}
                  accept=".pcap,.cap,.pcapng"
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                <button
                  type="submit"
                  className="mt-4 w-full px-4 py-2 font-semibold text-white bg-green-600 rounded-md hover:bg-green-700"
                >
                  Analyze File
                </button>
              </form>
              {uploadStatus && (
                <p className="mt-4 text-sm text-center text-gray-600">
                  {uploadStatus}
                </p>
              )}
            </div>
            <div className="bg-white p-6 rounded-lg shadow-xl">
              <h2 className="text-xl font-bold text-gray-800 mb-4">
                About This Project
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                VoIP Tracer is an intelligence platform that analyzes network
                metadata to detect and flag suspicious VoIP activity in
                real-time, even when encrypted.
              </p>
              <a
                href="https://github.com/johnhomelander/voip-tracer"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center w-full px-4 py-2 font-semibold text-white bg-gray-800 rounded-md hover:bg-gray-900"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.168 6.839 9.49.5.092.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.031-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.378.203 2.398.1 2.651.64.7 1.03 1.595 1.03 2.688 0 3.848-2.338 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.001 10.001 0 0022 12c0-5.523-4.477-10-10-10z"
                    clipRule="evenodd"
                  />
                </svg>
                View on GitHub
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

// --- PAGE COMPONENT ---
// This decides whether to show the Login form or the Dashboard
export default function HomePage() {
  const { token, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading Application...
      </div>
    );
  }

  return token ? <Dashboard /> : <LoginForm />;
}
