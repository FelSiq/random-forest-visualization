import { Component, OnInit, Input, ElementRef } from '@angular/core';

import * as d3 from 'd3-selection';
import * as d3Zoom from 'd3-zoom';
import * as d3Drag from 'd3-drag';

import { DTInterface, TreeInterface } from '../../../dt-interface';

@Component({
  selector: 'app-tree-d3-model',
  templateUrl: './tree-d3-model.component.html',
  styleUrls: ['./tree-d3-model.component.css'],
})
export class TreeD3ModelComponent implements OnInit {
  @Input() treeNodes: DTInterface[];
  chosenTree: string | number;

  private svg: any;
  private links: any;
  private nodes: any;
  private width: number;
  private height: number;
  private readonly radiusMinimum: number = 8;
  private readonly radiusScaleFactor: number = 16;
  private static readonly styleColorLinkDefault = 'rgb(128, 128, 128)';
  private static readonly styleColorLinkSelected = 'rgb(0, 0, 0)';

  constructor(private eleRef: ElementRef) { }

  ngOnInit() {
    this.chosenTree = '0';
    this.changesHandler();
  }

  changesHandler(): void {
    this.initSvg();
    this.createTree();
  }

  private static formatLinkId(nodeAId: number,
                       nodeBId: number,
                       addIdHash: boolean = false): string {
    return (addIdHash ? '#' : '') + 'link-' + nodeAId + '-' + nodeBId;
  }

  private static formatNodeId(nodeId: number, addIdHash: boolean = false): string {
    return (addIdHash ? '#' : '') + 'node-' + nodeId;
  }

  private initSvg() {
    this.svg = d3.select('svg');

    this.cleanSvg();

    this.links = this.svg.append('g')
        .attr('class', 'group-links');

    this.nodes = this.svg.append('g')
        .attr('class', 'group-nodes')

    this.svg.call(d3Zoom.zoom()
      .scaleExtent([0.5, 3])
      .translateExtent([[0, 0], [this.width, this.height]])
      .on('zoom', () => {
        this.svg
          .attr('transform', d3.event.transform);
      }));

    this.width = (
        +this.svg.attr('width') ?
        +this.svg.attr('width') :
        this.eleRef.nativeElement.offsetWidth
    );

    this.height = (
        +this.svg.attr('height') ?
        +this.svg.attr('height') :
        this.eleRef.nativeElement.offsetHeight
    );
  }

  private cleanSvg(): void {
    if (this.nodes) {
      this.nodes.selectAll('*').remove();
    }

    if (this.links) {
      this.links.selectAll('*').remove();
    }
  }

  private createTree(): void {
    if (!this.svg || !this.treeNodes) {
      return;
    }

    const chosenTree = +this.chosenTree;
    const curTreeNodes = this.treeNodes[chosenTree];

    if (!(curTreeNodes.hasOwnProperty('tree_'))) {
      return;
    }

    const curTree = curTreeNodes.tree_.value as TreeInterface;

    this.buildNode(
        curTree,
        0,
        -1,
        this.width / 2,
        this.width / 4,
        0.02 * this.height,
        0.98 * this.height / (1 + curTree.max_depth));

  }

  private generateLink(nodeAId: number,
                       nodeBId: number,
                       x1: number,
                       x2: number,
                       y1: number,
                       y2: number): void {

    this.links.append('line')
      .classed('link', true)
      .attr('id', TreeD3ModelComponent.formatLinkId(nodeAId, nodeBId))
      .attr('x1', x1)
      .attr('x2', x2)
      .attr('y1', y1)
      .attr('y2', y2)
      .style('stroke-width', 2)
      .style('stroke', TreeD3ModelComponent.styleColorLinkDefault);
  }

  private connectNodes(nodeAId: number, nodeBId: number): void {
    const nodeA = this.nodes.select(TreeD3ModelComponent.formatNodeId(nodeAId, true));
    const nodeB = this.nodes.select(TreeD3ModelComponent.formatNodeId(nodeBId, true));

    this.generateLink(
      nodeAId,
      nodeBId,
      nodeA.attr('cx'),
      nodeB.attr('cx'),
      nodeA.attr('cy'),
      nodeB.attr('cy'));
  }

  private generateNode(nodeId: number,
                       cx: number,
                       cy: number,
                       radius: number,
                       parentId: number,
                       sonLeftId: number,
                       sonRightId: number): void {
    this.nodes.append('circle')
      .classed('node', true)
      .attr('id', TreeD3ModelComponent.formatNodeId(nodeId)) 
      .attr('index', nodeId)
      .attr('stroke', 'gray')
      .attr('fill', 'white')
      .attr('cx', cx)
      .attr('cy', cy)
      .attr('r', radius)
      .attr('sonLeftId', sonLeftId)
      .attr('sonRightId', sonRightId)
      .attr('parentId', parentId)
      .on('mouseenter', function() {
        const node = d3.select(this);

        node.attr('stroke-width', 2)
            .attr('stroke', 'black');

        d3.select('#node-info-pannel')
          .attr('selected-node', node.attr('index'));
      })
      .on('mouseleave', function() {
        d3.select(this)
          .attr('stroke-width', 1)
          .attr('stroke', 'gray');

        d3.select('#node-info-pannel')
          .attr('selected-node', -1);
      })
      .call(d3Drag.drag()
        .on('start', function() {
          const node = d3.select(this);

          const nodeId = +node.attr('index');
          const parentId = +node.attr('parentId');
          const sonLeftId = +node.attr('sonLeftId');
          const sonRightId = +node.attr('sonRightId');

          node
            .raise()
            .classed('node-active', true)
            .attr('r', 1.25 * radius);

          d3.selectAll([
                TreeD3ModelComponent.formatLinkId(nodeId, sonLeftId, true),
                TreeD3ModelComponent.formatLinkId(nodeId, sonRightId, true),
                TreeD3ModelComponent.formatLinkId(parentId, nodeId, true),
            ].join(','))
              .classed('link-active', true)
              .style('stroke', TreeD3ModelComponent.styleColorLinkSelected);
        })
        .on('end', function() {
          const node = d3.select(this);

          const nodeId = +node.attr('index');
          const parentId = +node.attr('parentId');
          const sonLeftId = +node.attr('sonLeftId');
          const sonRightId = +node.attr('sonRightId');

          node
            .classed('node-active', false)
            .attr('r', radius);

          d3.selectAll([
                TreeD3ModelComponent.formatLinkId(nodeId, sonLeftId, true),
                TreeD3ModelComponent.formatLinkId(nodeId, sonRightId, true),
                TreeD3ModelComponent.formatLinkId(parentId, nodeId, true),
            ].join(','))
              .classed('link-active', false)
              .style('stroke', TreeD3ModelComponent.styleColorLinkDefault);
        })
        .on('drag', function() {
          const node = d3.select(this);

          const nodeId = +node.attr('index');
          const parentId = +node.attr('parentId');
          const sonLeftId = +node.attr('sonLeftId');
          const sonRightId = +node.attr('sonRightId');

          node
            .attr('cx', d3.event.x)
            .attr('cy', d3.event.y);

          d3.selectAll([
                TreeD3ModelComponent.formatLinkId(nodeId, sonLeftId, true),
                TreeD3ModelComponent.formatLinkId(nodeId, sonRightId, true),
            ].join(','))
              .attr('x1', d3.event.x)
              .attr('y1', d3.event.y);

          d3.select(TreeD3ModelComponent.formatLinkId(parentId, nodeId, true))
            .attr('x2', d3.event.x)
            .attr('y2', d3.event.y);
        }));
  }

  private buildNode(
        curTree: TreeInterface,
        nodeId: number,
        parentId: number,
        cx: number,
        cxDelta: number,
        cy: number,
        cyDelta: number): void {

      const sonLeftId = +curTree.children_left[nodeId];
      const sonRightId = +curTree.children_right[nodeId];

      const radius = (
        this.radiusMinimum +
        this.radiusScaleFactor *
        (+curTree.weighted_n_node_samples[nodeId] /
        +curTree.weighted_n_node_samples[0]));

      this.generateNode(
          nodeId,
          cx,
          cy,
          radius,
          parentId,
          sonLeftId,
          sonRightId);

      if (sonLeftId >= 0 && sonLeftId < curTree.capacity) {
        const cxSonLeft = cx - cxDelta;
        const cySonLeft = cy + cyDelta;

        this.buildNode(
            curTree,
            sonLeftId,
            nodeId,
            cxSonLeft,
            cxDelta / 2,
            cySonLeft,
            cyDelta);

        this.connectNodes(nodeId, sonLeftId);
      }

      if (sonRightId >= 0 && sonRightId < curTree.capacity) {
        const cxSonRight = cx + cxDelta;
        const cySonRight = cy + cyDelta;

        this.buildNode(
            curTree,
            sonRightId,
            nodeId,
            cxSonRight,
            cxDelta / 2,
            cySonRight,
            cyDelta);

        this.connectNodes(nodeId, sonRightId);
      }
  }

}
