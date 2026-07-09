import React, { useRef, useEffect, useState } from 'react';

// ==============================================================================
// TopicGraph — D3 Force-Directed Graph per argomenti e moduli
// ==============================================================================

export default function TopicGraph({ topics, onSelectTopic }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 });

  // Update dimensions on resize
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Build graph data from topics
  const graphData = React.useMemo(() => {
    const nodes = [];
    const links = [];
    const topicIds = new Set();

    for (const topic of topics) {
      const nodeId = `topic-${topic.id}`;
      nodes.push({
        id: nodeId,
        label: topic.name,
        type: 'topic',
        data: topic,
        r: 22
      });
      topicIds.add(topic.id);

      for (const mod of (topic.modules || [])) {
        const modId = `mod-${topic.id}-${mod.number}`;
        nodes.push({
          id: modId,
          label: mod.name,
          type: 'module',
          data: mod,
          topicId: topic.id,
          r: 14
        });
        links.push({ source: nodeId, target: modId });
      }
    }

    // Parent-child links
    for (const topic of topics) {
      if (topic.parent_id && topicIds.has(topic.parent_id)) {
        links.push({
          source: `topic-${topic.parent_id}`,
          target: `topic-${topic.id}`,
          type: 'parent'
        });
      }
    }

    return { nodes, links };
  }, [topics]);

  // D3 rendering
  useEffect(() => {
    if (!svgRef.current || topics.length === 0) return;

    // Dynamically import D3
    import('d3').then(d3 => {
      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const { nodes, links } = graphData;
      if (nodes.length === 0) return;

      // Define arrow markers
      const defs = svg.append('defs');
      defs.selectAll('marker')
        .data(['parent'])
        .enter().append('marker')
        .attr('id', 'arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', 'rgba(210,153,34,0.3)')
        .attr('d', 'M0,-5L10,0L0,5');

      // Zoom behavior
      const zoom = d3.zoom()
        .scaleExtent([0.5, 3])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        });
      svg.call(zoom);

      const g = svg.append('g');

      // Simulation
      const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(dimensions.width / 2, dimensions.height / 2))
        .force('collision', d3.forceCollide().radius(d => d.r + 5));

      // Links
      const link = g.selectAll('.link')
        .data(links)
        .enter().append('line')
        .attr('class', d => `link ${d.type === 'parent' ? 'parent-link' : ''}`)
        .attr('stroke', d => d.type === 'parent' ? 'rgba(210,153,34,0.2)' : 'rgba(255,255,255,0.08)')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', d => d.type === 'parent' ? '4,3' : 'none');

      // Nodes
      const node = g.selectAll('.node')
        .data(nodes)
        .enter().append('circle')
        .attr('class', 'node')
        .attr('r', d => d.r)
        .attr('fill', d => d.type === 'topic' ? 'rgba(188,140,255,0.15)' : 'rgba(0,210,255,0.12)')
        .attr('stroke', d => d.type === 'topic' ? '#bc8cff' : '#00d2ff')
        .attr('stroke-width', 2)
        .call(d3.drag()
          .on('start', (event, d) => { simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on('end', (event, d) => { simulation.alphaTarget(0); d.fx = null; d.fy = null; }))
        .on('click', (event, d) => {
          setSelectedTopic(d.data);
          if (onSelectTopic) onSelectTopic(d.data);
        });

      // Labels
      const label = g.selectAll('.label')
        .data(nodes)
        .enter().append('text')
        .attr('class', 'label')
        .attr('text-anchor', 'middle')
        .attr('dominantBaseline', 'central')
        .attr('fill', '#e2e4eb')
        .attr('font-size', d => d.type === 'topic' ? '9px' : '7px')
        .attr('font-weight', d => d.type === 'topic' ? '600' : '400')
        .attr('pointer-events', 'none')
        .text(d => d.label.length > 15 ? d.label.slice(0, 14) + '…' : d.label);

      // Tick
      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        node
          .attr('cx', d => d.x)
          .attr('cy', d => d.y);

        label
          .attr('x', d => d.x)
          .attr('y', d => d.y + d.r + 8);
      });
    });
  }, [graphData, dimensions, onSelectTopic]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />
      {selectedTopic && onSelectTopic && (
        <div className="topic-selected-info" style={{
          padding: '12px',
          marginTop: '12px',
          background: 'rgba(188,140,255,0.08)',
          borderRadius: '8px',
          border: '1px solid rgba(188,140,255,0.2)'
        }}>
          <div style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '4px' }}>
            {selectedTopic.name}
          </div>
          <div style={{ fontSize: '0.65rem', color: '#8b8fa3' }}>
            {selectedTopic.description || 'Nessuna descrizione'}
          </div>
        </div>
      )}
    </div>
  );
}