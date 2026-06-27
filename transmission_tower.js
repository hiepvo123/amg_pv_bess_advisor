import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

export class TransmissionTower {

    #meshes = [];
    #towerInstances = [];
    #towerCount = 2;
    #towerMatrix;
    scene;

    constructor(scene, towerCount) {

        this.scene = scene;
        this.#towerCount = towerCount;
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
        object.scale.set( 0.006,0.006,0.006);
        object.position.set(0, 0, 7);

        object.updateMatrixWorld(true);

        object.traverse((child) => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                child.material = customMaterial;

                this.#meshes.push({
                    mesh: child,
                    matrix: child.matrixWorld.clone(),
                });
            }
        });



        
    }

    async addToScene(){
        this.#meshes.forEach(({ mesh, matrix }) => {   
            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                this.#towerCount
            );
                            
            im.castShadow = true;
            im.receiveShadow = true;
            im.userData.localMatrix = matrix.clone();
        
            this.scene.add(im);
            this.#towerInstances.push(im);
        });

        this.#towerMatrix = new THREE.Object3D();
        
        for(let i = 0; i < this.#towerCount; i++) {
            this.#towerMatrix.position.set(-(7) , 0 , -14*i);
                  
                    
            this.#towerMatrix.updateMatrix();
        
            this.#towerInstances.forEach((im) => {
                const finalMatrix = this.#towerMatrix.matrix.clone();
                finalMatrix.multiply(im.userData.localMatrix);
        
                im.setMatrixAt(i, finalMatrix);
                im.instanceMatrix.needsUpdate = true;
            }); 
        }
    }

    setTowerPos(index, position) {
        //console.log(position);

        this.#towerMatrix.position.set(position.x, position.y, position.z);

        //console.log(this.#towerMatrix.position);
        this.#towerMatrix.updateMatrix();

        const im = this.#towerInstances.at(index);
        const finalMatrix = this.#towerMatrix.matrix.clone();
        finalMatrix.multiply(im.userData.localMatrix);

        //console.log(finalMatrix);

        im.setMatrixAt(index, finalMatrix);
        im.instanceMatrix.needsUpdate = true;
    }

    getTowerMatrix(){
        return this.#towerMatrix;
    }


}
