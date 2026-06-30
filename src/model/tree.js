import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
export class Tree {
    mesh;
    meshes = [];

    constructor() {
        this.mesh = new THREE.Group();
    }
    async load() {
        const mtlLoader = new MTLLoader();
        const objLoader = new OBJLoader();

        const materials = await mtlLoader.loadAsync(
            './src/assets/Tree/Tree.mtl'
        );

        materials.preload();
        objLoader.setMaterials(materials);

        const object = await objLoader.loadAsync(
            './src/assets/Tree/Tree.obj'
        );

        object.traverse((child) => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                this.meshes.push(child);


                if (child.material.map) {
                    child.material.transparent = true;
                    child.material.alphaTest = 0.5;
                    child.material.side = THREE.DoubleSide;
                    child.material.needsUpdate = true;
                }
            }
        });

        object.scale.set(0.5, 0.5, 0.5);
        object.position.set(0, 0, 2);

        this.mesh.add(object);
    }
    

    getObject() {
        return this.mesh;
    }
}

