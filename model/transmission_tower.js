import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

export class TransmissionTower {
    mesh;
    meshes = [];

    constructor() {
        this.mesh = new THREE.Group();
    }
    async load() {
        const objLoader = new OBJLoader();

        const customMaterial = new THREE.MeshStandardMaterial({
            color: 'white',
            roughness: 0.4,
            metalness: 1.0
        });

        const object = await objLoader.loadAsync(
            './src/assets/17492_Electricity_Transmission_Tower_v1.obj'
        );

        object.rotateX(-Math.PI / 2);
        object.scale.set(0.006, 0.006, 0.006);
        object.position.set(0, 0, 7);

        object.updateMatrixWorld(true);

        object.traverse((child) => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                child.material = customMaterial;

                this.meshes.push({
                    mesh: child,
                    matrix: child.matrixWorld.clone(),
                });
            }
        });

        this.mesh.add(object);
    }

    getObject() {
        return this.mesh;
    }
}
