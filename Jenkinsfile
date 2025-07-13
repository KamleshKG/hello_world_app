pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk'
        PUB_CACHE = '/home/vagrant/VirtualBox/.pub-cache'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"
    }
    stages {
        stage('Set Permissions') {
            steps {
                sh '''
                # Set full permissions (TEST ENVIRONMENT ONLY)
                sudo chmod -R 777 /home/vagrant/VirtualBox
                sudo chmod -R 777 /opt/flutter
                sudo chown -R jenkins:jenkins /home/vagrant/VirtualBox
                sudo chown -R jenkins:jenkins /opt/flutter
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                flutter clean
                flutter pub get
                flutter build apk --release
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk'
                }
            }
        }

        stage('Publish to Artifactory') {
            when {
                expression { fileExists('build/app/outputs/flutter-apk/app-release.apk') }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        def version = sh(script: "grep 'version:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()
                        def appName = sh(script: "grep 'name:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()
                        
                        sh """
                        curl -H "Authorization: Bearer $TOKEN" \
                             -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/${appName}/${version}/app-release.apk" \
                             -T build/app/outputs/flutter-apk/app-release.apk
                        """
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "=== Permission Summary ==="
            ls -ld /home/vagrant/VirtualBox
            ls -ld /opt/flutter
            '''
        }
    }
}