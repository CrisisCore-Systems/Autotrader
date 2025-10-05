import type { ExecutionTreeNode } from '../types';

interface Props {
  node: ExecutionTreeNode;
}

function Outcome({ status }: { status: 'success' | 'failure' | 'skipped' | undefined }) {
  if (!status) {
    return <span className="status-pending">pending</span>;
  }
  return <span className={`status-${status}`}>{status}</span>;
}

function Node({ node }: { node: ExecutionTreeNode }) {
  return (
    <div className="tree-node">
      <div className="node-header">
        <span>{node.title}</span>
        <Outcome status={node.outcome?.status} />
      </div>
      {node.outcome?.summary ? <div className="node-summary">{node.outcome.summary}</div> : null}
      {node.children?.map((child) => (
        <Node key={child.key} node={child} />
      ))}
    </div>
  );
}

export function TreeView({ node }: Props) {
  return (
    <div className="tree-view">
      <Node node={node} />
    </div>
  );
}
