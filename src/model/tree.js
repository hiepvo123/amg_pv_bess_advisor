import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
export class Tree {
    mesh;
    meshes = [];
    instancedMeshes = [];
    treeCount = 400;
    treeMatrix;
    scene

    constructor(scene) {

        this.scene = scene;
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


    }

    async addToScene(){
        this.meshes.forEach((mesh) => {
            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                this.treeCount
            );

            im.castShadow = true;
            im.receiveShadow = true;

            this.scene.add(im);
            this.instancedMeshes.push(im);
        });

        const treeMatrix = new THREE.Object3D();
        treeMatrix.scale.set(0.5,0.5,0.5);

        const clearRadius = 15; // empty square from -10 to 10

        for (let i = 0; i < this.treeCount; i++) {
            let x, z;

            do {
                x = Math.random() * 100 - 50;
                z = Math.random() * 100 - 50;
            } while (
                Math.abs(x) < clearRadius &&
                Math.abs(z) < clearRadius
            );

            treeMatrix.position.set(x, 0, z);
            //treeMatrix.scale.set(0.75,0.75,0.75);
            
            //treeMatrix.rotation.y = Math.random() * Math.PI * 2;

            treeMatrix.updateMatrix();

            this.instancedMeshes.forEach((im) => {
                im.setMatrixAt(i, treeMatrix.matrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }
    }

}

