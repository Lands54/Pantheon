import { NodeInspector } from '../components/NodeInspector'

export function GalaxyInspectorPanel(props) {
  return (
    <section className="panel galaxy-side-panel inspector">
      <NodeInspector {...props} />
    </section>
  )
}
