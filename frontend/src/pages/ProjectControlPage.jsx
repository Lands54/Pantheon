import { useState } from 'react'

export function ProjectControlPage({ projectId, onCreateProject, onSetRunning, isRunning }) {
  const [newProjectId, setNewProjectId] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const create = async () => {
    setStatus('')
    setError('')
    try {
      const id = newProjectId.trim()
      if (!id) throw new Error('project id is required')
      await onCreateProject(id)
      setStatus(`Created project: ${id}`)
      setNewProjectId('')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const setRunning = async (running) => {
    setStatus('')
    setError('')
    try {
      await onSetRunning(projectId, running)
      setStatus(running ? 'Project started' : 'Project stopped')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <h3>Project Lifecycle</h3>
        <div className="row-between">
          <div>Current Project: <span className="mono">{projectId}</span></div>
          <div>Status: <span className={`chip ${isRunning ? 'ok' : 'off'}`}>{isRunning ? 'Running' : 'Stopped'}</span></div>
        </div>
        <div className="action-row top-gap">
          <button className="primary-btn" onClick={() => setRunning(true)}>Start</button>
          <button className="ghost-btn" onClick={() => setRunning(false)}>Stop</button>
        </div>
      </div>

      <div className="panel">
        <h3>Create Project</h3>
        <div className="action-row">
          <input value={newProjectId} onChange={(e) => setNewProjectId(e.target.value)} placeholder="new_project_id" />
          <button className="primary-btn" onClick={create}>Create & Switch</button>
        </div>
      </div>

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
