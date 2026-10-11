import { Component, createRef, type ErrorInfo, type ReactNode } from 'react'
import { displayFailureMessage } from './errorBoundaryCopy'

type BoundaryState = {
  error: Error | null
  retrySequence: number
}

type Props = {
  children: ReactNode
  scope: string
  className?: string
}

/**
 * Isolates display failures from the traffic provider and command callbacks.
 * React error boundaries intentionally do not catch event-handler or async errors.
 */
export class DisplayErrorBoundary extends Component<Props, BoundaryState> {
  state: BoundaryState = { error: null, retrySequence: 0 }
  private readonly heading = createRef<HTMLHeadingElement>()

  static getDerivedStateFromError(error: Error): Pick<BoundaryState, 'error'> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Do not include telemetry, command payloads, or raw backend responses in diagnostics.
    console.error('[Urban Grid] Display boundary captured a render error.', {
      scope: this.props.scope,
      errorName: error.name || 'Error',
      componentStack: info.componentStack?.split('\n').slice(0, 4).join('\n') ?? '',
    })
  }

  componentDidMount() {
    if (this.state.error) this.heading.current?.focus()
  }

  componentDidUpdate(_: Props, previousState: BoundaryState) {
    if (!previousState.error && this.state.error) this.heading.current?.focus()
  }

  retry = () => this.setState((current) => ({ error: null, retrySequence: current.retrySequence + 1 }))

  private reload = () => window.location.reload()

  render() {
    if (!this.state.error) return <div className={this.props.className ?? 'display-boundary-content'} key={this.state.retrySequence}>{this.props.children}</div>

    return <section className="display-error-boundary" role="alert" aria-live="assertive">
      <span className="panel-label">DISPLAY RECOVERY</span>
      <h2 ref={this.heading} tabIndex={-1}>A display component needs attention</h2>
      <p>{displayFailureMessage(this.props.scope)}</p>
      <p className="display-error-note">No traffic command was repeated. Retry only reloads this display area.</p>
      <div className="display-error-actions">
        <button type="button" onClick={this.retry}>Retry display</button>
        <button type="button" className="secondary" onClick={this.reload}>Reload application</button>
      </div>
    </section>
  }
}
