export function createSessionStore(storage, keys) {
    function read() {
        let user = null;
        const savedUser = storage.getItem(keys.user);
        if (savedUser) {
            try {
                user = JSON.parse(savedUser);
            } catch (error) {
                storage.removeItem(keys.user);
            }
        }
        return {
            access: storage.getItem(keys.access) || "",
            refresh: storage.getItem(keys.refresh) || "",
            user,
        };
    }

    function write({ access = "", refresh = "", user = null }) {
        storage.setItem(keys.access, access);
        storage.setItem(keys.refresh, refresh);
        storage.setItem(keys.user, JSON.stringify(user));
    }

    function writeAccess(access) {
        storage.setItem(keys.access, access);
    }

    function writeUser(user) {
        storage.setItem(keys.user, JSON.stringify(user));
    }

    function clear() {
        storage.removeItem(keys.access);
        storage.removeItem(keys.refresh);
        storage.removeItem(keys.user);
    }

    return { read, write, writeAccess, writeUser, clear };
}
