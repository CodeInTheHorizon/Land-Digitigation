import { useState, type FormEvent } from "react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await register(email, password, fullName);
      navigate("/login");
    } catch (caughtError) {
      if (!axios.isAxiosError(caughtError)) {
        setError("Unable to create your account. Please try again.");
      } else if (!caughtError.response) {
        setError("The registration service is unavailable. Please start the backend and try again.");
      } else if (caughtError.response.status === 409) {
        setError("This email is already registered. Please sign in instead.");
      } else {
        const detail = caughtError.response.data?.detail;
        setError(typeof detail === "string" ? detail : "Registration failed. Please check your details and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-center mb-2">🏛️ Land Records</h1>
        <p className="text-sm text-slate-500 text-center mb-6">
          Create an account for the Digitization System
        </p>
        {error && (
          <div role="alert" className="bg-red-50 text-red-600 text-sm p-3 rounded-lg mb-4">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="full-name" className="block text-sm font-medium mb-1">Full name</label>
            <input
              id="full-name"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              minLength={1}
              maxLength={255}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
            />
          </div>
          <div>
            <label htmlFor="register-email" className="block text-sm font-medium mb-1">Email</label>
            <input
              id="register-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
            />
          </div>
          <div>
            <label htmlFor="register-password" className="block text-sm font-medium mb-1">Password</label>
            <input
              id="register-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              maxLength={128}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
            />
            <p className="text-xs text-slate-500 mt-1">Use at least 8 characters.</p>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 text-white py-2 rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Creating account…" : "Create Account"}
          </button>
        </form>
        <p className="text-sm text-center mt-4 text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-600 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}