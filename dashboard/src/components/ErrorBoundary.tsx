import { Component } from 'preact'
import type { ComponentChildren } from 'preact'

interface Props {
  fallback?: ComponentChildren
  children: ComponentChildren
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div class="p-4 border border-error/30 bg-error/10 text-error text-sm rounded">
          Something went wrong: {this.state.error.message}
        </div>
      )
    }
    return this.props.children
  }
}
