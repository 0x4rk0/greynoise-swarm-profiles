/* jslint browser: true, indent: 4, maxlen: 80 */

(function() {
    const crc16Table = [
        0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
        0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
        0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
        0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
        0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
        0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
        0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
        0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
        0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
        0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
        0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
        0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
        0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
        0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
        0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
        0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
        0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
        0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
        0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
        0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
        0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
        0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
        0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
        0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
        0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
        0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
        0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
        0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
        0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
        0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
        0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
        0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
    ];
    const crc16kermit = function(buf) {
        let crc = 0x0000;
        for (let index = 0; index < buf.length; index++) {
            const byte = buf[index];
            crc = (crc16Table[(crc ^ byte) & 0xff] ^ (crc >> 8)) & 0xffff;
        }
        return crc;
    };
    const convertToStr = function(unitArr) {
        let myString = '';
        for (let i = 0; i < unitArr.byteLength; i++) {
            if (unitArr[i] !== 0) {
                myString += String.fromCharCode(unitArr[i]);
            }
        }
        return myString;
    };

    const xor16 = function(a, b, len) {
        let i = 0;
        for (; i < len; i++)
        { a[i] ^= (b[i] ^ 0xa5); }
    };

    const equal = function(a, b) {
        const length = a.byteLength;
        if (a.byteLength !== b.byteLength) {
            return false;
        }
        for (let i = 0; i < length; i++) {
            if (a[i] !== b[i]) {
                return false;
            }
        }
        return true;
    };
    const getPlatforms = function(packageData) {
        let platforms = [];
        if (packageData.platformsFlag != undefined) {
            const isSS = (packageData.platformsFlag & 32) > 0;
            const isE3 = (packageData.platformsFlag & 64) > 0;
            const isCompulab = (packageData.platformsFlag & 128) > 0;
            if (isCompulab) {
                platforms = ["GT1000"];
            } else if ((!isSS && !isE3) || (isSS && !isE3)) {
                // Old package could be used for SS only.
                // (Old package has no flags, so isSS and isE3 are false).
                platforms = ["Site Supervisor"];
            } else if (isE3 && !isSS) {
                platforms = ["E3"];
            } else {
                platforms = ["Site Supervisor", "E3"];
            }
        } else {
            if (packageData.schemaNumber === 6) {
                platforms = ["E2", "E2E"];
            } else if (packageData.schemaNumber === 5) {
                platforms = ["E2E"];
            } else {
                platforms = ["E2"];
            }
        }

        return platforms;
    };

    const readStringFromE2Package = function(file, offsetObj) {
        let result = null;
        let dataView = new DataView(file);
        const stringLength = dataView.getUint32(offsetObj.offset, true);
        if (stringLength > 0) {
            result = convertToStr(new Uint8Array(file, offsetObj.offset + 4, stringLength));
        }
        offsetObj.offset += stringLength + 4;
        return result;
    };

    const readElementsFromE2Package = function(file, resultObj) {
        let dataView = new DataView(file);
        resultObj.elementCount = dataView.getUint16(resultObj.offset, true);
        resultObj.offset += 2;
        resultObj.files = [];
        resultObj.subpackages = [];
        for (let i = 0; i < resultObj.elementCount; i++) {
            const element = {};
            element.name = readStringFromE2Package(file, resultObj);
            element.targetPath = readStringFromE2Package(file, resultObj);
            element.targetSystem = dataView.getUint8(resultObj.offset, true);
            resultObj.offset += 1;
            if (resultObj.schemaNumber === 1) {
                element.isPackage = dataView.getUint8(resultObj.offset, true);
            } else {
                element.type = dataView.getUint8(resultObj.offset, true);
            }

            resultObj.offset += 1;
            element.CRC = dataView.getUint16(resultObj.offset, true);
            resultObj.offset += 2;
            element.fileOffset = dataView.getUint32(resultObj.offset, true);
            resultObj.offset += 4;
            element.dataSize = dataView.getUint32(resultObj.offset, true);
            resultObj.offset += 4;

            if (element.isPackage == 1 || element.type == 3) {
                resultObj.subpackages.push(element);
            } else {
                resultObj.files.push(element);
            }
        }
    };

    const readE2Package = function(file, offset, result) {
        let dataView = new DataView(file);
        result.offset = offset;
        result.headerLength = dataView.getUint32(result.offset, true);
        result.offset += 4;

        result.headerLength = dataView.getUint16(result.offset, true);
        result.offset += 2;

        result.minUSVersioin = readStringFromE2Package(file, result);
        result.minE2Version = readStringFromE2Package(file, result);
        result.schemaNumber = dataView.getUint32(result.offset, true);
        result.offset += 4;
        result.packageType = readStringFromE2Package(file, result);
        result.packageVersion = readStringFromE2Package(file, result);
        switch (result.schemaNumber) {
            case 1:
            case 2:
                readElementsFromE2Package(file, result);
                result.containsPatch = 0;
                result.patchFromVersion = "";
                result.languageID = 1;
                break;
            case 3:
            case 5:
            case 6:
                result.containsPatch = dataView.getUint8(result.offset, true);
                result.offset += 1;
                result.patchFromVersion = readStringFromE2Package(file, result);
                result.languageID = dataView.getUint16(result.offset, true);
                result.offset += 2;
                readElementsFromE2Package(file, result);
                break;
            case 4:
                result.containsPatch = dataView.getUint8(result.offset, true);
                result.offset += 1;
                result.patchFromVersion = readStringFromE2Package(file, result);
                result.languageID = dataView.getUint16(result.offset, true);
                result.offset += 2;
                result.featureID = dataView.getUint32(result.offset, true);
                result.offset += 4;
                readElementsFromE2Package(file, result);
                break;
            default:
                result.error = "unknow schema number";
                break;
        }

        delete result.offset;
        let subPackage, subPackageOffset;
        if (result.schemaNumber === 6) {
            // Read E2 package
            subPackage = result.subpackages.find(item => item.name === "E2 Firmware Update");
            if (subPackage) {
                subPackageOffset = offset + subPackage.fileOffset;
                readE2Package(file, subPackageOffset, subPackage);
            }

            // Read E2E package
            subPackage = result.subpackages.find(item => item.name === "E2E Firmware Update");
            if (subPackage) {
                subPackageOffset = offset + subPackage.fileOffset;
                readE2Package(file, subPackageOffset, subPackage);
            }
        } else {
            subPackage = result.subpackages.find(item => item.name === "E2 Firmware");
            if (subPackage) {
                subPackageOffset = offset + subPackage.fileOffset;
                readE2Package(file, subPackageOffset, subPackage);
                result.FWPackage = subPackage;
            }
        }

        return result;
    };

    const getE2FWPackageVersion = function(package) {
        let version;
        if (package.schemaNumber === 6 ) {
            let subPackageForE2 = package.subpackages.find(item => item.name === "E2 Firmware Update");
            let subPackageForE2E = package.subpackages.find(item => item.name === "E2E Firmware Update");
            version = subPackageForE2.FWPackage.packageVersion + "(E2), " + subPackageForE2E.FWPackage.packageVersion + "(E2E)";
        } else {
            version = package.FWPackage.packageVersion;
        }

        return version;
    };

    const checkE2Package = function(package) {
        let isValid;
        let checkSinglePackage =  function (singlePackage) {
            return singlePackage.FWPackage && singlePackage.FWPackage.packageVersion;
        };

        if (package.schemaNumber === 6) {
            let subPackageForE2 = package.subpackages.find(item => item.name === "E2 Firmware Update");
            let subPackageForE2E = package.subpackages.find(item => item.name === "E2E Firmware Update");
            isValid = subPackageForE2 && subPackageForE2E && checkSinglePackage(subPackageForE2) &&　checkSinglePackage(subPackageForE2E);
        } else {
            isValid = checkSinglePackage(package);
        }

        return isValid;
    };

    const uint8ArrayToHex = (uint8Array) => {
        return Array.prototype.map.call(uint8Array, (byte) => {
            return ('0' + (byte & 0xFF).toString(16)).slice(-2);
        }).join('');
    }

    self.addEventListener('message', function(e) {
        let data = e.data, reader, result, len,
            ver16, xorOrig, total, xor,
            sig16, version, tmp, i, file;
        switch (data.cmd) {
            case 'start':
                self.postMessage({'ack': 'started'});
                result = {isVaild: false};
                try {
                    file = data.file;
                    total = file.byteLength;
                    result.size = total;
                    if (total === 0) {
                        self.postMessage({'ack': 'done', 'data':result});
                        return;
                    }
                    // read struct updater_header_s in updater.h
                    sig16 = new Uint8Array(file, 0, 16);
                    ver16 = new Uint8Array(file, 16, 16);
                    xorOrig = new Uint8Array(file, 32, 16);
                    result.ver = convertToStr(ver16);
                    result.type = convertToStr(new Uint8Array(file, 0, 4));
                    xor = new Uint8Array(16);
                    // skip the updater_header_
                    i = 16 + 16 + 16 + 4 + 4 + 512 - 40;
                    // crc job
                    // heavily work maybe need to move web worker.
                    while (i < total) {
                        len = total - i;
                        if (len > 16) {
                            len = 16;
                        }
                        tmp = new Uint8Array(file, i, len);
                        xor16(xor, tmp, len);
                        i += 16;
                    }
                    xor16(xor, sig16, 16);
                    xor16(xor, ver16, 16);
                    if (equal(xor, xorOrig)) {
                        result.isVaild = true;
                        result.platformsFlag = new DataView(file).getUint32(48, true);
                        if (xorOrig) {
                            result.crc = uint8ArrayToHex(xorOrig).toUpperCase();
                        }
                    } else {
                        result = {isVaild: false};
                        result.crc = crc16kermit(new Uint8Array(file)) + "";

                        readE2Package(file, 0, result);
                        result.isVaild = !result.error && checkE2Package(result);
                        if (result.isVaild) {
                            result.ver = getE2FWPackageVersion(result);
                        }
                    }

                    if (result.isVaild) {
                        result.platforms = getPlatforms(result);
                    }
                    self.postMessage({'ack': 'done', 'data': result});
                } catch (err) {
                    self.postMessage({
                        'ack': 'exception',
                        'err': err.toString()
                    });
                }
                break;
            case 'destory':
                self.postMessage({'ack': 'destoryed'});
                self.close(); // Terminates the worker.
                break;
            default:
                self.postMessage({'ack':'unknown'});
        }
    }, false);
}(self));
