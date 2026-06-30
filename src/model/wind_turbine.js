import * as THREE from 'three';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
export class WindTurbine {
    mesh;
    blades;
    meshes = [];
    scene;
    instancedTurbines = [];
    bladeInstances =[];
    bladeInstancesMatrix;
    turbinePositions = [];
    bladeRotation = 0;
    count;

    constructor(scene) {
        
        this.scene = scene;
        for (let i = 0; i < 2; i++) {
            this.turbinePositions.push(
                new THREE.Vector3(5, 8.2, 8 + 5 * i) //collumn 1
            );
        }

        for (let i = 2; i < 4; i++) {
            this.turbinePositions.push(
                new THREE.Vector3(13, 8.2, 8 + 5 * (3 - i)) //collum 2
            );
        }

        this.count = this.turbinePositions.length;

        //Indices
        //0     5
        //1     6
        //2     7
        //3     8
        //4     9
        
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
                this.meshes.push({
                    mesh: child,
                    matrix: child.matrixWorld.clone()
                });
              //child.receiveShadow = true; 
            }
        });
        
        
    }

    async addToScene() {
        this.meshes.forEach(({mesh,matrix}) => {
            //console.log(
            //    mesh.name,
            //    mesh.position,
            //    mesh.rotation
            //);

            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                this.count
            );

            im.castShadow = true;
            im.userData.localMatrix = matrix.clone();
            //im.receiveShadow = true;

            if (mesh.name === 'WindTurbine_Blades001_Material002_0') {
                this.bladeInstances.push(im) ;
            } else {
                this.instancedTurbines.push(im);
            }

            this.scene.add(im);

        });

        const bodyTurbineMatrix = new THREE.Object3D();
        this.bladeInstancesMatrix = new THREE.Object3D();
        bodyTurbineMatrix.scale.set(2,2,2);
        this.bladeInstancesMatrix.scale.set(2,2,2);

        for (let i = 0; i < this.turbinePositions.length; i++) {
            bodyTurbineMatrix.position.copy(this.turbinePositions[i]);
            
            bodyTurbineMatrix.updateMatrix();

            this.instancedTurbines.forEach((im) => {
                const finalMatrix = bodyTurbineMatrix.matrix.clone();
                finalMatrix.multiply(im.userData.localMatrix);
                im.setMatrixAt(i, finalMatrix);
                im.instanceMatrix.needsUpdate = true;
            });

            //bladeInstances.setMatrixAt(i, bladeDummy.matrix);
        }
    }

    updateBlades(speed = 0.01) {
        this.bladeRotation += speed;

        const dummy = new THREE.Object3D();
        dummy.scale.set(2, 2, 2);

        for (let i = 0; i < this.turbinePositions.length; i++) {
            dummy.position.copy(this.turbinePositions[i]);

            // turbine orientation
            dummy.rotation.set(
                0,
                0,
                this.bladeRotation
            );

            dummy.updateMatrix();

            this.bladeInstances.forEach((im) => {
                const finalMatrix = dummy.matrix.clone();
                finalMatrix.multiply(im.userData.localMatrix);

                im.setMatrixAt(i, finalMatrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }


    }

    getObject() {
        return this.mesh;
    }
}
