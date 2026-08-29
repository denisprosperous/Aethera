"""Pure-Python SMACOF solver (matches Rust aethera-geometer/smacof.rs)."""
import numpy as np

def classical_mds(delta, dim=2):
    n = delta.shape[0]
    d2 = delta ** 2
    row_mean = d2.mean(axis=1, keepdims=True)
    col_mean = d2.mean(axis=0, keepdims=True)
    total = d2.mean()
    B = -0.5 * (d2 - row_mean - col_mean + total)
    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]; eigvecs = eigvecs[:, order]
    coords = np.zeros((n, dim))
    for k in range(dim):
        if eigvals[k] > 0: coords[:, k] = eigvecs[:, k] * np.sqrt(eigvals[k])
    coords -= coords.mean(axis=0)
    return coords

def smacof(delta, weight=None, dim=2, max_iter=500, tol=1e-12):
    n = delta.shape[0]
    if weight is None:
        weight = np.ones((n, n)); np.fill_diagonal(weight, 0)
    V = -weight.copy(); np.fill_diagonal(V, weight.sum(axis=1))
    J = np.ones((n, n)) / n
    Vp = np.linalg.inv(V + J) - J
    X = classical_mds(delta, dim)
    X -= X.mean(axis=0)
    prev = float("inf"); stress = float("inf")
    for it in range(max_iter):
        dis = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=2)
        dis_safe = np.where(dis < 1e-30, 1e-30, dis)
        c = weight * delta / dis_safe; np.fill_diagonal(c, 0)
        B = -c; np.fill_diagonal(B, c.sum(axis=1))
        X = Vp @ (B @ X); X -= X.mean(axis=0)
        new_dis = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=2)
        diff = new_dis - delta
        num = float((weight * diff * diff).sum() / 2)
        denom = float((weight * delta * delta).sum() / 2)
        stress = float(np.sqrt(num / max(denom, 1e-30)))
        rel = abs(prev - stress) / max(prev, 1e-30)
        conv = rel
        prev = stress
        if rel < tol: break
    return X, stress, conv

def discrete_gaussian_curvature(coords, adj):
    n = len(adj); curv = np.zeros(n)
    for i in range(n):
        neigh = adj[i]
        if len(neigh) < 3: continue
        diffs = coords[neigh] - coords[i]
        angles = np.arctan2(diffs[:, 1], diffs[:, 0])
        order = np.argsort(angles)
        sorted_n = [neigh[j] for j in order]
        sum_a = 0.0; m = len(sorted_n)
        for k in range(m):
            k1 = (k + 1) % m
            a = sorted_n[k]; b = sorted_n[k1]
            r_a = np.linalg.norm(coords[a] - coords[i])
            r_b = np.linalg.norm(coords[b] - coords[i])
            c_ab = np.linalg.norm(coords[a] - coords[b])
            if r_a < 1e-12 or r_b < 1e-12: continue
            cos_t = (r_a**2 + r_b**2 - c_ab**2) / (2 * r_a * r_b)
            sum_a += np.arccos(float(np.clip(cos_t, -1.0, 1.0)))
        curv[i] = 2 * np.pi - sum_a
    return curv
