import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-400">
                Something went wrong rendering this section
              </p>
              {this.state.error && (
                <p className="mt-1 text-xs text-red-400/70">
                  {this.state.error.message}
                </p>
              )}
              <button
                onClick={this.handleRetry}
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300"
              >
                <RotateCcw className="h-3 w-3" />
                Retry
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
