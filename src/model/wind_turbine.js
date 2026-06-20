import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
export class WindTurbine {
    mesh;
    blades;

    constructor() {
        this.mesh = new THREE.Group();
    }

    async load() {
        const gltfLoader = new GLTFLoader();
        const gltf = await gltfLoader.loadAsync('./src/assets/scene.gltf');
        //TODO: THIS MODEL NORMALS ARE FUCKED UP
        gltf.scene.traverse((child) => {
          console.log(child)
            if (child.isMesh) {
              //const helper = new VertexNormalsHelper(child, 0.5, 0xff0000 );
              //child.add(helper);
              child.castShadow = true;
              //child.receiveShadow = true; 
            }
        });
        
        
        this.blades = gltf.scene.getObjectByName('WindTurbine_Blades001');
        gltf.scene.position.set(0,4.1,0);
        
        this.mesh.add(gltf.scene);
        this.mesh.scale.set(1.5,1.5,1.5);
    }

    getObject() {
        return this.mesh;
    }
}
