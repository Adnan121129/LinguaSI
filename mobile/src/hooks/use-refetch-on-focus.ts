import { useFocusEffect } from "expo-router";
import { useCallback, useRef } from "react";

/** Tab screens stay mounted; refresh their data when the learner comes back to them. */
export function useRefetchOnFocus(refetch: () => unknown) {
  const firstFocus = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (firstFocus.current) {
        firstFocus.current = false;
        return;
      }
      refetch();
    }, [refetch]),
  );
}
