"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <DefaultFallback error={this.state.error} onRetry={() => this.setState({ hasError: false })} />;
    }
    return this.props.children;
  }
}

function DefaultFallback({ error, onRetry }: { error?: Error; onRetry: () => void }) {
  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-xl border border-red-100 bg-red-50 p-8 text-center">
      <p className="text-sm font-semibold text-red-800">Something went wrong</p>
      {error?.message && (
        <p className="max-w-sm text-xs text-red-600">{error.message}</p>
      )}
      <div className="flex gap-3">
        <button
          onClick={onRetry}
          className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Try again
        </button>
        <button
          onClick={() => window.location.reload()}
          className="rounded-md px-3 py-1.5 text-xs text-red-500 hover:text-red-700"
        >
          Reload page
        </button>
      </div>
    </div>
  );
}
