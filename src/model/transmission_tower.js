import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
export class TransmissionTower {
    mesh;

    constructor() {
        this.mesh = new THREE.Group();
        const objLoader = new OBJLoader();
        const customMaterial = new THREE.MeshStandardMaterial({
            color: 'white', // Red
            roughness: 0.4,
            metalness: 1.0
        });

        objLoader.load('./src/assets/17492_Electricity_Transmission_Tower_v1.obj', (object) => {
        
            object.traverse((child) => {
                if (child.isMesh) {
                    child.castShadow = true;
                    child.receiveShadow = true;
                    child.material = customMaterial;
                }
            });

        object.rotateX(-Math.PI / 2);
        object.scale.set(0.003, 0.003, 0.003);
        object.position.set(0, 0, 7);

        this.mesh.add(object);
    }
);
    }

    getObject() {
        return this.mesh;
    }
}
