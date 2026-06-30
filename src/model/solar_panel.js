import * as THREE from 'three';

export class SolarPanel {
    
    panel;
    meshes = [];
    solarPanelInstances = [];
    #solarBaseInstances = [];
    solarPanelCount = 36;
    solarPanelInstancesMatrix;
    solarBaseMatrix;
    scene;
    panelPositions = [];

    constructor(scene) {
        this.scene = scene;
        this.mesh = new THREE.Group();

        // Pole
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.05, 0.05, 2, 8),
            new THREE.MeshPhongMaterial({ color: 0x666666 })
        );
        pole.position.y = 1;
      
;

        // Mount
        const mount = new THREE.Mesh(
            new THREE.BoxGeometry(0.1, 0.3, 0.1),
            new THREE.MeshPhongMaterial({ color: 0x555555 })
        );
        mount.position.y = 2.1;

        this.panel = new THREE.Group();

  
        const panelMaterial =new THREE.MeshPhongMaterial({
                color: 0x1a2f5a,
                shininess: 100,
            });
        var texture = new THREE.TextureLoader().load('./src/assets/solar_panel_texture.jpeg');
        panelMaterial.map = texture;

        // Solar panel
        const panel = new THREE.Mesh(
            new THREE.BoxGeometry(2, 1.2, 0.05),
            panelMaterial
            
        );

        //panel.position.y = 2.4;
        //panel.rotation.x = -Math.PI / 6; // 30° tilt
        pole.updateMatrix();
        panel.updateMatrix();
        this.panel.add(mount);
        this.panel.add(panel);

        this.meshes.push({
            mesh: pole,
            matrix: pole.matrix.clone(),
            type: 'pole'
        });

        this.meshes.push({
            mesh: panel,
            matrix: panel.matrix.clone(),
            type: 'panel'
        });
        for (let x = 5; x <= 10; x++) {
            for (let z = 0; z <= 5; z++) {
                this.panelPositions.push(
                    new THREE.Vector3(x * 2.5 - 15, 1, -z * 3)
                );
            }
        }


        
    }

    addToScene() {
        this.meshes.forEach(({ mesh, matrix, type }) => {
            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                this.solarPanelCount
            );
            im.castShadow = true;
            im.receiveShadow = true;
        
            // Save the local matrix
            im.userData.localMatrix = matrix.clone();
            if (type === 'panel'){
                this.solarPanelInstances.push(im);
            } else{
                this.#solarBaseInstances.push(im);
            }
            this.scene.add(im);
        });
        
        
        this.solarPanelInstancesMatrix = new THREE.Object3D();
        this.solarBaseMatrix = new THREE.Object3D();
        

    }

    setBasePosition(index, position){
;

        const dummy = new THREE.Object3D();
        dummy.position.copy(position);
        dummy.updateMatrix();

        this.#solarBaseInstances.forEach((im) => {
            const finalMatrix = dummy.matrix.clone();
            finalMatrix.multiply(im.userData.localMatrix);

            im.setMatrixAt(index, finalMatrix);
        });
    }

    setPanelPosition(index, position) {

               
        const dummy = new THREE.Object3D();
        dummy.position.copy(position);
        dummy.updateMatrix();
        
        this.solarPanelInstances.forEach((im) => {
            const finalMatrix = dummy.matrix.clone();
            finalMatrix.multiply(im.userData.localMatrix);

            im.setMatrixAt(index, finalMatrix);
        });
    }

    setPanelRotation(rotation) {
        const dummy = new THREE.Object3D();

        for (let i = 0; i < this.solarPanelCount; i++) {
            const matrix = new THREE.Matrix4();

            
            dummy.rotation.copy(rotation);
            dummy.updateMatrix();

            this.solarPanelInstances.forEach((im) => {
                const finalMatrix = dummy.matrix.clone();
                finalMatrix.multiply(im.userData.localMatrix);

                im.setMatrixAt(i, finalMatrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }
    }

    setBases() {
        const dummy = new THREE.Object3D();

        for (let i = 0; i < this.solarPanelCount; i++) {
            dummy.position.copy(this.panelPositions[i]);
            dummy.position.y -=2;

            dummy.updateMatrix();

            this.#solarBaseInstances.forEach((im) => {
                const finalMatrix = dummy.matrix.clone();
                finalMatrix.multiply(im.userData.localMatrix);

                im.setMatrixAt(i, finalMatrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }
    }

    lookAtPanels(target) {
        const dummy = new THREE.Object3D();

        for (let i = 0; i < this.solarPanelCount; i++) {
            dummy.position.copy(this.panelPositions[i]);
            dummy.lookAt(target);
            dummy.updateMatrix();

            this.solarPanelInstances.forEach((im) => {
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