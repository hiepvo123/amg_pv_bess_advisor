//import * as THREE from 'three';
import { App } from './control/app.js';

const app = new App();
await app.init();
app.update();
