import { Component, OnInit, Input } from '@angular/core';
import { DTInterface } from '../../dt-interface';

@Component({
  selector: 'app-tree-displayer',
  templateUrl: './tree-displayer.component.html',
  styleUrls: ['./tree-displayer.component.css'],
})
export class TreeDisplayerComponent implements OnInit {
  @Input() treeModel: DTInterface;

  constructor() { }

  ngOnInit() { }

  filter_empty(item): boolean {
    return item === 0 || item;
  }

  isArray(item): boolean {
    return item in Array;
  }
}
