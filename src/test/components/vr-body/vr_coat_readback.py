"""Compare the owned player's live lighting materials with proven DDS winners."""

HEAD_SHAPES = {'head', 'head_clawhead', 'head_clawhead_clawears'}


def texture_path(value):
    return value.replace('\\', '/').casefold() if isinstance(value, str) else ''


def verify_managed_fur(audit, verified_paths):
    """Check diffuse texture objects without making a framebuffer claim."""
    age = audit.get('ageMs')
    if audit.get('schema') != 1 or type(age) not in (int, float) or not 0 <= age <= 2000:
        raise ValueError('A current version-1 coat audit is required')
    paths = {texture_path(path) for path in verified_paths}
    surfaces = []
    for row in audit['surfaces']:
        if row['managed'] is not True and row['name'].casefold() not in HEAD_SHAPES:
            continue
        path = texture_path(row['diffusePath'])
        resource = texture_path(row['diffuseResource'])
        surfaces.append({'name': row['name'], 'diffusePath': path, 'diffuseResource': resource,
                         'managed': row['managed'] is True,
                         'vfsVerified': bool(path) and path in paths,
                         'textureObjectMatches': bool(path) and path == resource})
    names = {row['name'].casefold() for row in surfaces}
    expected_body = ('body' in names and bool(names & {'head', 'head_clawhead'})
                     and any(name.startswith('fur_') for name in names))
    verified = expected_body and all(row['vfsVerified'] and row['textureObjectMatches'] for row in surfaces)
    return {'materialTextureObjectsVerified': verified, 'bodyHeadAndFurObserved': expected_body,
            'surfaces': surfaces}
