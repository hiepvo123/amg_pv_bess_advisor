import * as THREE from 'three';

export class SolarPanel {
    
    panel;
    meshes = [];
    solarPanelInstances = [];
    solarBaseInstances = [];
    solarPanelCount = 36;
    solarPanelInstancesMatrix;
    solarBaseMatrix;
    scene;

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
                this.solarBaseInstances.push(im);
            }
            this.scene.add(im);
        });
        
        
        this.solarPanelInstancesMatrix = new THREE.Object3D();
        this.solarBaseMatrix = new THREE.Object3D();
        
        let index = 0;
        
        for (let x = 5; x <= 10; x++) {
            for (let z = 0; z <= 5; z++) {
                this.solarBaseMatrix.position.set(x*2.5 -15, -1, -z*3);
                this.solarBaseMatrix.updateMatrix();
        
                this.solarBaseInstances.forEach((im) => {
                    const finalMatrix = this.solarBaseMatrix.matrix.clone();
                    finalMatrix.multiply(im.userData.localMatrix);
        
                    im.setMatrixAt(index, finalMatrix);
                    im.instanceMatrix.needsUpdate = true;
                });
             
                index++; 
            }
                
        }
    }

    setPos(index, position){
        this.solarBaseMatrix.position.set(position.x, position.y, position.z);
        this.solarBaseMatrix.updateMatrix();
        const imBase = this.solarBaseInstances.at(index);
        const finalBaseMatrix = this.solarBaseMatrix.matrix.clone();
        finalBaseMatrix.multiply(im.userData.localMatrix);

        im.setMatrixAt(index, finalBaseMatrix);
        
        this.solarPanelInstancesMatrix.position.set(position.x, position.y, position.z);
        this.solarPanelInstancesMatrix.updateMatrix();
        const imPanel = this.solarPanelInstances.at(index);
        const finalPanelMatrix = this.solarPanelInstancesMatrix.matrix.clone();
        finalPanelMatrix.multiply(im.userData.localMatrix);

        im.setMatrixAt(index, finalPanelMatrix);
        
    }

    getObject() {
        return this.mesh;
    }
}