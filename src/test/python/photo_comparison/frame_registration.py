"""Offline diagnostics of unchanged original frames. Never writes image pixels."""
from pathlib import Path
import argparse, hashlib, json, math
import cv2
import numpy as np
from PIL import Image

PIXEL_ADMISSION_FIELDS = (
    'noActorsOrShadowsInRegions', 'staticWallAndGroundDetailsConfirmed',
    'noHudClippingOrOverlap', 'underwearFullBodiesEarsTailFeetConfirmed',
    'nativeOriginalQualityAccepted',
)

def require(value, message):
    if not value: raise ValueError(message)

def estimate(reference, current, policy):
    require(reference.shape == current.shape == (1080, 1920), 'Exact original FHD grids required')
    source, target, details = [], [], []
    for region in policy['regions']:
        x0, y0, x1, y1 = region['rectangle']
        require(0 <= x0 < x1 <= 1920 and 0 <= y0 < y1 <= 1080, 'Invalid fixed ROI')
        mask = np.zeros(reference.shape, dtype=np.uint8); mask[y0:y1, x0:x1] = 255
        corners = cv2.goodFeaturesToTrack(reference, 80, 0.02, 7, mask=mask, blockSize=7)
        require(corners is not None and len(corners) >= policy['minimumCornersPerRegion'],
                'Static ROI has insufficient distinctive corners: ' + region['id'])
        moved, status, error = cv2.calcOpticalFlowPyrLK(reference, current, corners, None,
            winSize=(21, 21), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 40, 0.001))
        back, reverse, unused = cv2.calcOpticalFlowPyrLK(current, reference, moved, None,
            winSize=(21, 21), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 40, 0.001))
        good = ((status.ravel() == 1) & (reverse.ravel() == 1) &
                (np.linalg.norm(corners.reshape(-1,2)-back.reshape(-1,2), axis=1) <= 0.15))
        require(int(good.sum()) >= policy['minimumCornersPerRegion'],
                'Static ROI registration is ambiguous: ' + region['id'])
        a, b = corners.reshape(-1,2)[good], moved.reshape(-1,2)[good]
        delta = b-a
        max_delta = float(np.linalg.norm(delta, axis=1).max())
        mean_luma = abs(float(current[y0:y1,x0:x1].mean())-float(reference[y0:y1,x0:x1].mean()))
        mae = float(np.abs(current[y0:y1,x0:x1].astype(float)-reference[y0:y1,x0:x1]).mean())
        details.append({'id':region['id'], 'surface':region['surface'], 'corners':int(good.sum()),
                        'medianDeltaPixels':np.median(delta,axis=0).tolist(),
                        'maximumFeatureDisplacementPixels':max_delta,
                        'meanLuminanceDifference':mean_luma, 'rawMeanAbsoluteDifference':mae})
        source.extend(a); target.extend(b)
    require({r['surface'] for r in details} == {'wall','ground'}, 'Both wall and ground anchors required')
    # Estimate a full affine transform solely as a diagnostic. No warp/resampling occurs.
    matrix, inliers = cv2.estimateAffine2D(np.float32(source), np.float32(target),
        method=cv2.RANSAC, ransacReprojThreshold=0.25, maxIters=2000, confidence=0.999, refineIters=20)
    require(matrix is not None and inliers is not None and int(inliers.sum()) >= 24,
            'Global static-scene transform is unobservable')
    corners = np.array([[0,0,1],[1919,0,1],[0,1079,1],[1919,1079,1]],dtype=float)
    displacement = corners @ matrix.T - corners[:,:2]
    maximum = float(np.linalg.norm(displacement,axis=1).max())
    passed = maximum <= policy['maximumDisplacementPixels'] and all(
        r['maximumFeatureDisplacementPixels'] <= policy['maximumDisplacementPixels'] and
        r['meanLuminanceDifference'] <= policy['maximumMeanLuminanceDifference'] and
        r['rawMeanAbsoluteDifference'] <= policy['maximumRawMeanAbsoluteDifference'] for r in details)
    return {'passed':passed,'affineReferenceToCurrent':matrix.tolist(),
            'translationPixels':matrix[:,2].tolist(),
            'rotationDegrees':math.degrees(math.atan2(matrix[1,0],matrix[0,0])),
            'maximumFhdCornerDisplacementPixels':maximum,'regions':details,
            'imagesShiftedResampledOrWritten':False}

def run(case_path, roi_path):
    case_path, roi_path = Path(case_path), Path(roi_path)
    case = json.loads(case_path.read_text(encoding='utf-8-sig'))
    policy = json.loads(roi_path.read_text(encoding='utf-8-sig'))
    rows = case['photos']
    require(2 <= len(rows) <= 12 and len({r['id'] for r in rows}) == len(rows) and
            all(r['status']=='captured' for r in rows), 'Two to twelve unique complete originals required')
    arrays, hashes = {}, {}
    for row in rows:
        path = Path(row['path']); data = path.read_bytes(); h = hashlib.sha256(data).hexdigest()
        require(h == row['sha256'], 'Original frame changed: ' + row['id'])
        with Image.open(path) as image:
            require(image.size == (1920,1080), 'Original resolution differs')
            arrays[row['id']] = np.asarray(image.convert('L'))
        hashes[row['id']] = h
    baseline = rows[0]['id']; results = []
    for row in rows[1:]:
        try: result = estimate(arrays[baseline], arrays[row['id']], policy)
        except (ValueError, cv2.error) as error: result = {'passed':False,'unavailable':str(error)}
        results.append({'baseline':baseline,'current':row['id'],**result})
    review = policy['rootReview']
    admitted = review['baselineSha256'] == hashes[baseline] and review.get('originalHashes') == hashes and all(
        review.get(key) is True for key in PIXEL_ADMISSION_FIELDS) and all(
        value is True for key,value in review.items() if key not in ('baselineSha256','originalHashes'))
    return {'schemaVersion':1, 'status':'PASS_STATIC_BACKGROUND_REGISTRATION' if
            admitted and all(r['passed'] for r in results) else 'COMPARE_WITHHELD',
            'rootPixelAndRoiAdmission':admitted,'originalHashes':hashes,'comparisons':results,
            'roiSourceSha256':hashlib.sha256(roi_path.read_bytes()).hexdigest(),
            'versions':{'opencv':cv2.__version__,'numpy':np.__version__},
            'scope':'Background geometric/photometric alignment only; bone/anchor continuity and root pixel verdict remain required.',
            'noImagesModified':True}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--rois',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();target=Path(args.output)
    require(not target.exists(), 'Never overwrite a prior registration verdict')
    result=run(args.case,args.rois);target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'])
