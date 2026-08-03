import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Helm render error:", error, info);
  }

  retry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#09090b] grain p-6">
          <div className="relative z-10 max-w-md w-full text-center">
            <div className="w-12 h-12 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center mx-auto mb-6">
              <span className="font-mono text-gold font-medium">H</span>
            </div>
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">Something went wrong</p>
            <h1 className="text-2xl font-light text-white tracking-tight">This screen hit an unexpected error.</h1>
            <p className="text-sm text-zinc-500 mt-3 leading-relaxed">
              You can try again. If it keeps happening, refresh the page or sign back in.
            </p>
            <button
              data-testid="error-retry-btn"
              onClick={this.retry}
              className="mt-8 rounded-md bg-gold text-black font-medium text-sm px-5 py-2.5 transition-colors hover:bg-gold-hover"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
