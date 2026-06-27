import * as THREE from 'three';

export class PowerPole {
    mesh;

    constructor() {
        this.mesh = new THREE.Group();

        // Main pole
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.08, 0.12, 5, 8),
            new THREE.MeshPhongMaterial({ color: 0x8b6b4a })
        );
        pole.position.y = 2.5;
        this.mesh.add(pole);

        // Crossbar
        const crossbar = new THREE.Mesh(
            new THREE.BoxGeometry(2.5, 0.1, 0.1),
            new THREE.MeshPhongMaterial({ color: 0x555555 })
        );
        crossbar.position.y = 4.5;
        this.mesh.add(crossbar);
    }

    getObject() {
        return this.mesh;
    }
}